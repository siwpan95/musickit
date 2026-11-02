"""
程序入口 — musickit 专属版（音频混音，已去除视频合成功能）。

两种运行方式：
  1. 图形界面（默认）：
        python main.py
  2. 命令行随机混音（phonk 风格，从 bass / drum / guita 随机选音）：
        python main.py --remix [--count N] [--seed S] [--out DIR] [--format wav|mp3]

phonk 风格参考（联网调研）：
  典型 phonk beat 由多层构成 —— 鼓组（1~2 轨）、808 贝斯（1 轨）、
  牛铃 / 旋律采样（1 轨）、人声切片（可选）、其它 synth / 采样。
  最小可用骨架为 3 轨：drum + bass + guita（旋律），
  典型完整制作约 4~6 轨。本工具默认随机选 3 条（每类各 1 条），
  可用 --count 调整到 4~5 条。
"""

import argparse
import json
import os
import random
import re
import sys

import numpy as np

# 确保脚本所在目录在 sys.path，便于 import core / gui / utils
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# =========================================================================
# pydub 使用项目内置 ffmpeg / ffprobe（bin/ 优先，其次系统 PATH）
# 必须在 import pydub 之前把 bin/ 加入 PATH，否则 import 时 pydub 找不到
# ffmpeg 会发出 RuntimeWarning。
# 解析统一走 core.binfind，且**只在确实存在时才覆盖** pydub 的指向 —— 无条件
# 覆盖会把 converter 指到一个不存在的路径，连「系统装了 ffmpeg」也用不了，
# 并且会污染同进程内其它入口（GUI / 测试）的全局状态。
# =========================================================================
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_BIN_DIR = os.path.join(_PROJECT_ROOT, "bin")

import pydub  # noqa: E402

from core import binfind as _binfind  # noqa: E402

# 把 bin/ 前置到 PATH 交给 binfind 统一处理（幂等）。
# 这里原先是 `os.environ["PATH"] = _BIN_DIR + ...` 直写：main.py 会被 GUI、
# hourly_remix、测试等多处以不同模块名重复加载，每加载一次 PATH 就多一段
# 相同的 bin/（实测 3 次加载 → 41 段变 44 段），越跑越长。
_binfind.ensure_path_env()

_FFMPEG_PATH = _binfind.resolve("ffmpeg")
_FFPROBE_PATH = _binfind.resolve("ffprobe")

# 只覆盖真实存在的 converter；pydub 0.25.1 无 `AudioSegment.ffprobe` 属性，
# 它靠 which("ffprobe") 走 PATH（上面已把 bin/ 前置）。
if _FFMPEG_PATH:
    pydub.AudioSegment.converter = _FFMPEG_PATH

# =========================================================================
# 发布级交付规格（2026-09-17 起生效，面向网易云音乐）
#   平台要求：码率 > 320 kbps、采样率 > 44.1 kHz、单文件 < 200 MB。
#   有损编码上限就是 mp3 320 kbps，永远达不到「> 320 kbps」，
#   因此对外交付一律走无损（默认 WAV）。
#   默认交付：WAV / 48 kHz / 24 bit / 立体声 = 2304 kbps；120s ≈ 34.6 MB。
# =========================================================================
DELIVERY_SPEC = {
    "sample_rate": 48000,
    "bit_depth": 24,
    "channels": 2,
    "max_size_mb": 200,
}
LOSSLESS_FORMATS = {"wav", "flac"}
# 有损兜底：仍导出时给到该格式的上限码率（mp3/ogg/aac 最高 320k）
LOSSY_BITRATE = {"mp3": "320k", "ogg": "320k", "aac": "320k"}

# 引擎版本：影响声音的实现变更必须递增（会记入每首的 recipe.engine，便于漂移归因）
REMIX_VERSION = "2.1.0"

from core import musical_key  # noqa: E402
from core.loop_slicer import bar_ms, duration_ms, duration_ms_or  # noqa: E402


# =========================================================================
# 依赖检查（在创建 tk 窗口前完成）
# =========================================================================
_MISSING = []

try:
    from pydub import AudioSegment  # noqa: F811
except ImportError:
    _MISSING.append("pydub")

# Python 3.13+ 移除了标准库 audioop，pydub 运行时依赖它，
# 需要通过 audioop-lts 补丁包提供。
try:
    import audioop
except ImportError:
    try:
        import audioop_lts  # audioop-lts 暴露的兼容模块
    except ImportError:
        _MISSING.append("audioop-lts")

if _MISSING:
    import tkinter.messagebox as mb

    msg = (
        "缺少依赖: " + ", ".join(_MISSING) + "\n\n"
        "请运行：pip install -r requirements.txt\n\n"
        "注意：\n"
        "  - 使用 Python 3.13+ 时必须安装 audioop-lts（pydub 依赖 audioop）。"
    )
    print("错误：" + msg, file=sys.stderr)
    # 尝试弹窗（如果 tk 可用）
    try:
        mb.showerror("缺少依赖", msg)
    except Exception:
        pass
    sys.exit(1)


# musickit 素材目录（与 remix 项目同级；可用环境变量 MUSICKIT_ROOT 覆盖，F5）
_MUSICKIT_ROOT = os.environ.get("MUSICKIT_ROOT") or os.path.dirname(_PROJECT_ROOT)
if not os.path.isdir(_MUSICKIT_ROOT):
    raise FileNotFoundError(
        f"素材根目录不存在: {_MUSICKIT_ROOT}\n"
        f"可通过环境变量 MUSICKIT_ROOT 指定 musickit 根目录。"
    )
_SOURCE_CATEGORIES = [
    "bass", "drum", "guita", "cowbell", "synth", "acapella",
    "animal", "sfx",
    # 新增：37 类目补齐（keys/strings/brass/woodwind/ethnic）
    "keys", "strings", "brass", "woodwind", "ethnic",
]

# phonk 最小骨架：鼓 + 贝斯 + 旋律（guita），优先各取 1 条；
# 牛铃(cowbell)与 synth/采样为 phonk 标志层，数量充足时一并纳入。
_PHONK_SKELETON = ["drum", "bass", "guita"]

# 随机模式只用短素材池；acapella 为整首人声（数分钟），不进随机 one-shot
_RANDOM_POOLS = ["bass", "drum", "guita", "cowbell", "synth", "animal", "sfx"]

# 骨架层（必须提供连续律动的层）：选音时保底挑选 >=1 小节的 loop 素材，
# 混音时强制 ROLE_LOOP，杜绝 one-shot 被降级为稀疏点缀导致整曲无鼓/无贝斯律动。
_SKELETON_CATS = {"drum", "bass", "guita"}

# --release-safe 允许的授权层级：free/pack 可用于对外发布；restricted/unknown 仅个人使用。
# 【已废弃 2026-11-02】原 --release-safe 的放行层级。素材均为公共领域，
# 该过滤已移除；常量保留供历史脚本/文档引用，不再参与任何判定。
_RELEASE_SAFE_TIERS = {"free", "pack"}


# =========================================================================
# 混音师风格接入（与 burbidge_album/mixer_styles.py 共享固定风格链）
# 固定风格（专辑端 10 位混音师）与随机风格（本引擎）的整合点：
#   --mixer-style <slug|random> 可选启用；不启用时行为与之前完全一致。
# =========================================================================
_MIXER_ROLE_TO_BUS = {
    "drum": "drums", "cowbell": "drums",
    "bass": "bass",
    "synth": "pad", "keys": "pad", "strings": "pad",
    "brass": "pad", "woodwind": "pad", "ethnic": "pad",
    "guita": "lead", "vocal": "lead",
    # sfx / animal / other：不挂总线着色，保持冲击力
}


def _load_mixer_style(name, rng):
    """加载混音师风格（burbidge_album/mixer_styles.py）。

    Returns:
        (style_dict, irs_dict, ms_module)；风格不可用时 (None, None, None)。
    """
    try:
        bp = os.path.join(_MUSICKIT_ROOT, "burbidge_album")
        if bp not in sys.path:
            sys.path.insert(0, bp)
        import mixer_styles as ms
    except Exception as e:
        print(f"[remix] 混音师风格不可用（{e}），本次跳过风格着色", file=sys.stderr)
        return None, None, None
    try:
        st = ms.resolve_style(name, rng)
    except KeyError as e:
        raise SystemExit(str(e))
    return st, ms.style_irs(st["reverb"]), ms


def _seg_to_np(seg):
    seg = seg.set_frame_rate(44100).set_channels(2).set_sample_width(2)
    arr = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    return arr.reshape(-1, 2)


def _np_to_seg(x):
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=44100, sample_width=2, channels=2)


def _style_segment(seg, style, irs, bus_key, ms):
    """把一条素材切片的音色替换为该风格对应总线链（不应用总线电平级，
    保留混音引擎自身的角色水位平衡）。"""
    x = _seg_to_np(seg)
    y = ms.bus_chain(x, style[bus_key], irs, apply_level=False)
    return _np_to_seg(y)


def _apply_delivery_spec(segment, fmt: str,
                         sample_rate: int | None = None,
                         bit_depth: int | None = None,
                         channels: int | None = None):
    """把混合好的段落规格化到「发布级交付格式」。

    无损（wav/flac）用 48 kHz / 24 bit；有损（mp3/ogg/aac）用 48 kHz / 16 bit
    + 上限码率。返回 ``(segment, spec)``，``spec`` 含 sample_rate / bit_depth /
    channels / codec / kbps。

    ⚠️ pydub 的 ``set_sample_width(3)`` 会被静默升成 32-bit（实测），所以 24-bit
    只能靠导出时显式指定 ``pcm_s24le`` 编码器实现，不能直接靠 set_sample_width。
    """
    fmt = (fmt or "wav").lower()
    sr = int(sample_rate or DELIVERY_SPEC["sample_rate"])
    ch = int(channels or DELIVERY_SPEC["channels"])
    lossless = fmt in LOSSLESS_FORMATS
    depth = int(bit_depth or DELIVERY_SPEC["bit_depth"]) if lossless else 16

    codec = None
    parameters = None
    if fmt == "wav":
        codec = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_s32le"}.get(depth, "pcm_s24le")
    elif fmt == "flac":
        # FLAC 位深由输入采样格式决定：>=24bit 时把 ffmpeg 输入抬到 s32
        # （FLAC 编码器最高支持到 24/32bit 样本）
        parameters = ["-sample_fmt", "s32"] if depth >= 24 else None

    if not lossless or depth != 16:
        # 有损固定 16bit；无损 24/32bit 由 ffmpeg 编码器决定最终位深
        segment = segment.set_channels(ch)
    else:
        segment = segment.set_channels(ch).set_sample_width(2)
    segment = segment.set_frame_rate(sr)

    return segment, {
        "sample_rate": sr,
        "bit_depth": depth,
        "channels": ch,
        "codec": codec,
        "parameters": parameters,
        "kbps": round(sr * depth * ch / 1000.0, 1),
    }


class MixValidationError(RuntimeError):
    """导出前后的断言失败（空音频 / 静音 / 时长异常 / 文件不可读）。

    这类产物历史上会「正常报成功」：`--bars -1` 曾产出 102 字节、0 帧的空 WAV
    并打印「已保存至」。把断言放在导出**前**（内存对象）与导出**后**（落盘文件）
    两处，才能堵住「参数没生效」被误当成「艺术选择」。
    """


def _positive_int(text: str) -> int:
    """argparse 类型：必须是 >= 1 的整数。"""
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"需要整数，收到 {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"必须 >= 1，收到 {value}")
    return value


def _bpm_int(text: str) -> int:
    """argparse 类型：BPM 必须是 20~400 的整数（0 会让 bar_ms 除零）。"""
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"需要整数，收到 {text!r}") from None
    if not 20 <= value <= 400:
        raise argparse.ArgumentTypeError(f"BPM 需在 20~400，收到 {value}")
    return value


def _validate_mix(mix, bpm: int, bars: int) -> None:
    """导出前断言：拒绝空 / 静音 / 时长异常的混音结果。

    同时对 bpm/bars 做下界检查：CLI 已用 argparse 拦住非法值，但 GUI、提示词
    桥接器、电台渲染器都是**编程调用** run_remix，绕过了 argparse。
    """
    if bars < 1:
        raise MixValidationError(f"bars 非法：{bars}（必须 >= 1）")
    if bpm <= 0:
        raise MixValidationError(f"bpm 非法：{bpm}（必须 > 0）")
    total_ms = len(mix)
    frames = mix.frame_count() if hasattr(mix, "frame_count") else total_ms
    if total_ms <= 0 or frames <= 0:
        raise MixValidationError(
            f"混音结果为空（{total_ms}ms / {frames} frames），已中止导出"
            f"（bpm={bpm}，bars={bars}）"
        )
    peak = mix.max_dBFS
    if peak is None or peak == float("-inf") or peak < -90.0:
        raise MixValidationError(
            f"混音结果静音（峰值 {peak} dBFS），已中止导出（bpm={bpm}，bars={bars}）"
        )
    expected_ms = bar_ms(bpm, bars)
    # 容差：至少 1 小节的宽度，且不小于 2%（淡出/取整/结尾补齐都会带来小幅偏差）
    tolerance = max(bar_ms(bpm), int(expected_ms * 0.02))
    if expected_ms > 0 and abs(total_ms - expected_ms) > tolerance:
        raise MixValidationError(
            f"混音时长异常：实际 {total_ms}ms，期望 {expected_ms}ms"
            f"（bpm={bpm}，bars={bars}，容差 {tolerance}ms），已中止导出"
        )


def _verify_exported(path: str, bpm: int, bars: int) -> None:
    """导出后断言：文件必须存在、非空、可被读回且时长合理。

    不能只信「export 没抛异常」—— 空 WAV（102 字节 / 0 帧）同样能写成功。
    """
    if not os.path.isfile(path):
        raise MixValidationError(f"导出失败：文件不存在 {path}")
    size = os.path.getsize(path)
    if size < 512:  # 合法容器远大于此；曾观测到空 WAV 为 102 字节
        try:
            os.remove(path)
        finally:
            pass
        raise MixValidationError(f"导出产物过小（{size} 字节），已删除：{path}")
    probed = duration_ms(path)
    expected_ms = bar_ms(bpm, bars)
    if probed > 0 and expected_ms > 0:
        tolerance = max(bar_ms(bpm), int(expected_ms * 0.02))
        if abs(probed - expected_ms) > tolerance:
            raise MixValidationError(
                f"导出产物时长异常：回读 {probed}ms，期望 {expected_ms}ms"
                f"（容差 {tolerance}ms），文件保留待查：{path}"
            )


def _manifest_duration_ms(meta: dict | None) -> int:
    """从 manifest 条目取时长（毫秒）；缺失/非法返回 0。

    有了它，ffprobe 缺失时仍能走「已知时长」快路，不必退化成「时长恒 0」。
    """
    if not meta:
        return 0
    try:
        ms = int(round(float(meta.get("duration_s")) * 1000))
    except (TypeError, ValueError):
        return 0
    return ms if ms > 0 else 0


def _prefer_key_compatible(
    files: list[str],
    cat: str,
    entries: dict[str, dict],
    target: tuple[int | None, str | None] | None,
) -> tuple[list[str], list[str], dict[str, int]]:
    """按调性把候选分成 (兼容子集, 其余)，返回 (compatible, rest, 各档计数)。

    为什么用子集而不是排序：选音走 `pick_loop_candidate`，它是按时长/命名挑的，
    **不看列表顺序** —— 只重排等于没做（实测同种子下 --key C 与 --key F# 选出一模一样的曲子）。
    也不能硬过滤：池子小的时候会直接选不出音。故「有兼容子集就用子集，没有就退回全部」。
    """
    stats = {"same": 0, "relative": 0, "fifth": 0, "parallel": 0, "incompat": 0,
             "unknown": 0, "pitch_only": 0}
    if not target or not files:
        return [], list(files), stats

    pool = entries.get(cat, {})
    scored: list[tuple[int, int, str]] = []
    for i, path in enumerate(files):
        e = pool.get(os.path.basename(path)) or {}
        key_name, scale = e.get("key"), e.get("scale")
        conf = float(e.get("key_confidence") or 0.0)
        pc = musical_key.to_pc(key_name)
        rank_val: int | None = None
        if pc is not None and conf >= 0.05:
            # key_pitch_only 优先于 scale：它表示"音级确定、调式不适用"。
            # 反过来（先看 scale）会把两者混成假信息 —— 实测 Piano.ff.B5 被 chroma
            # 判成 C#m 写了 scale=minor，而文件名给出的音级是 B，
            # 于是条目变成"B 音级 + 小调"这种谁也没测出来的调式。
            if e.get("key_pitch_only"):
                rank_val = musical_key.rank_pitch(pc, target)
                stats["pitch_only"] += 1
            elif scale in ("major", "minor"):
                rank_val = musical_key.rank(target, (pc, scale))
        if rank_val is None:
            stats["unknown"] += 1
            # 未知排在「已知五度关系」之后：它可能合也可能不合，不该挤掉确定可用的
            scored.append((musical_key.RANK_PARALLEL, i, path))
            continue
        for name, val in (("same", musical_key.RANK_SAME), ("relative", musical_key.RANK_RELATIVE),
                          ("fifth", musical_key.RANK_FIFTH), ("parallel", musical_key.RANK_PARALLEL),
                          ("incompat", musical_key.RANK_INCOMPATIBLE)):
            if rank_val == val:
                stats[name] += 1
                break
        scored.append((rank_val, i, path))

    scored.sort(key=lambda t: (t[0], t[1]))
    # 兼容子集：同调 / 关系调 / 五度关系（rank <= RANK_FIFTH）
    compat = [p for r, _, p in scored if r <= musical_key.RANK_FIFTH]
    rest = [p for r, _, p in scored if r > musical_key.RANK_FIFTH]
    return compat, rest, stats


def _collect_category_files(category_dir: str) -> list[str]:
    """收集某类素材目录下的所有音频文件（含子类子目录，递归）。"""
    if not os.path.isdir(category_dir):
        return []
    files: list[str] = []
    for _root, _dirs, _names in os.walk(category_dir):
        for name in sorted(_names):
            lower = name.lower()
            if lower.endswith((".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff", ".aif")):
                files.append(os.path.join(_root, name))
    return files


def _load_pool_manifests(root: str) -> dict[str, dict[str, dict]]:
    """加载各素材池 manifest.json，返回 {category: {basename: entry}}。"""
    out: dict[str, dict[str, dict]] = {}
    for cat in _SOURCE_CATEGORIES:
        mp = os.path.join(root, cat, "manifest.json")
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            for e in data.get("entries", []):
                if isinstance(e, dict) and e.get("file"):
                    out.setdefault(cat, {})[e["file"]] = e
        except Exception:
            pass
    return out


def _filter_release_safe(
    files: list[str],
    cat: str,  # noqa: ARG001 —— 保留签名以兼容旧调用方
    entries: dict[str, dict[str, dict]],  # noqa: ARG001
    dropped: list[tuple[str, int]],  # noqa: ARG001
) -> list[str]:
    """【已废弃 2026-11-02】原 `--release-safe` 的 tier 过滤，现为恒等函数。

    废弃原因：本项目素材均为**公共领域（Public Domain）**，不存在需要隔离的
    版权素材；而 manifest 的 `license_tier` 本身严重失真（30,259 条中 64.7%
    是 unknown、仅 3.6% 标 restricted），据此过滤只会无谓地砍掉 68.3% 的可用
    素材，且该过滤还曾被 B 变体绕过 —— 保护为零、代价很大。

    保留函数仅为兼容 `music/prompt_driven_remix.py` 与
    `remix/tools/hourly_remix.py` 的现有 import（它们仍会调用）。
    行为：原样返回 files，不产生任何 dropped 记录。
    """
    return files


def pick_loop_candidate(
    files: list[str],
    bpm: int,
    rng: random.Random,
    entries: dict[str, dict] | None = None,
    max_probe: int = 60,
) -> str | None:
    """从候选列表挑一条 >=1 小节（可循环）的素材（骨架层保底）。

    1) manifest 已知时长 >= 0.9 小节：直接命中（零成本）；
    2) 未知时长：优先探测整曲 stem 命名（bass (N).wav 等），再随机抽样，
       用 ffprobe 探测时长，上限 max_probe 次；
    3) 全部不足时回退已探测的最长文件（宁要短 loop 也不要静音）。

    桥接器（prompt_driven_remix.py）复用同一选音口径。
    """
    if not files:
        return None
    min_ms = int(bar_ms(bpm) * 0.9)
    if entries:
        known = [f for f in files
                 if ((entries.get(os.path.basename(f)) or {}).get("duration_s") or 0)
                 >= min_ms / 1000.0]
        if known:
            return rng.choice(known)
    stems = [f for f in files
             if re.match(r"^(bass|drum|guita) \(\d+\)\.(wav|mp3|flac|aiff|aif)$",
                        os.path.basename(f), re.I)]
    rest = [f for f in files if f not in stems]
    rng.shuffle(rest)
    best = None
    best_dur = 0
    for path in (stems + rest)[:max_probe]:
        try:
            dur = duration_ms(path)
        except Exception:
            continue
        if dur > best_dur:
            best, best_dur = path, dur
        if dur >= min_ms:
            return path
    return best


def _pick_random_tracks(
    count: int,
    seed: int | None,
    bpm: int,
    entries: dict[str, dict[str, dict]] | None = None,
    release_safe: bool = False,
    target_key: tuple[int | None, str | None] | None = None,
) -> list[tuple[str, str]]:
    """按 phonk 风格随机挑选音轨。

    Returns:
        [(category, path), ...] 列表，长度 = count。
        优先保证 phonk 骨架 drum / bass / guita 各至少 1 条
        （骨架层用 pick_loop_candidate 保底选 >=1 小节 loop），
        其次尽量补入牛铃(cowbell)与 synth/采样这两类 phonk 标志层，
        剩余数量从全部素材随机补足（允许同类重复）。
    """
    rng = random.Random(seed)
    entries = entries or {}

    by_cat: dict[str, list[str]] = {}
    all_files: list[str] = []
    dropped: list[tuple[str, int]] = []
    key_stats: dict[str, int] = {}
    for cat in _RANDOM_POOLS:
        files = _collect_category_files(os.path.join(_MUSICKIT_ROOT, cat))
        if release_safe:
            files = _filter_release_safe(files, cat, entries, dropped)
        if target_key:
            compat, rest, st = _prefer_key_compatible(files, cat, entries, target_key)
            for k, v in st.items():
                key_stats[k] = key_stats.get(k, 0) + v
            if compat:
                files = compat
            else:
                # 该池无兼容素材 → 放宽到全部，并记一次「放宽」（否则会选不出音）
                files = compat + rest
                key_stats["relaxed"] = key_stats.get("relaxed", 0) + 1
        by_cat[cat] = files
        all_files.extend(files)

    if target_key:
        name = musical_key.format_target(target_key)
        compat = key_stats.get("same", 0) + key_stats.get("relative", 0) + key_stats.get("fifth", 0)
        print(f"[remix] 目标调性 {name}：兼容候选 {compat} 条"
              f"（同调 {key_stats.get('same', 0)} / 关系调 {key_stats.get('relative', 0)}"
              f" / 五度 {key_stats.get('fifth', 0)}）"
              f"，主音不同 {key_stats.get('parallel', 0)}，不兼容 {key_stats.get('incompat', 0)}"
              f"，未知 {key_stats.get('unknown', 0)}"
              + (f"｜{key_stats['relaxed']} 个池无兼容素材已放宽" if key_stats.get("relaxed") else ""))

    if release_safe and dropped:
        print("[remix] --release-safe：已剔除受限/未知授权素材 "
              + "、".join(f"{c} {n}" for c, n in dropped), file=sys.stderr)

    if not all_files:
        # 2026-11-02：原「被 --release-safe 全剔除」的分支已随过滤废弃而移除。
        raise FileNotFoundError(
            f"在 {_MUSICKIT_ROOT} 下未找到任何音频素材"
            f"（请确认 bass / drum / guita / cowbell / synth 目录中存在音频文件）。"
            f"可用 `python remix/tools/doctor.py` 检查各池 manifest 与磁盘是否一致。"
        )

    chosen: list[tuple[str, str]] = []

    # 1) 优先凑出 phonk 最小骨架（drum + bass + guita 各 1 条）：保底 >=1 小节 loop
    for cat in _PHONK_SKELETON:
        files = by_cat[cat]
        if not files:
            continue
        path = pick_loop_candidate(files, bpm, rng, entries.get(cat))
        if path:
            chosen.append((cat, path))

    # 2) 尽量补入 phonk 标志层：牛铃 + synth/采样 + 人声(动物叫) + SFX（各最多 1 条，避免喧宾夺主）
    for cat in ("cowbell", "synth", "animal", "sfx"):
        files = by_cat[cat]
        if files and len(chosen) < count:
            # animal 池（动物叫声 one-shot）作为「人声切片替代层」以 vocal 角色接入
            chosen.append(("vocal" if cat == "animal" else cat, rng.choice(files)))

    # 3) 剩余的 count 从全部素材随机补足（不打乱已选，允许同类重复）
    remaining = count - len(chosen)
    for _ in range(max(0, remaining)):
        path = rng.choice(all_files)
        cat = "other"
        # 用顶层池目录（路径第一段）判定类别，兼容任意深度的子类子目录
        rel = os.path.relpath(path, _MUSICKIT_ROOT).replace("\\", "/")
        top = rel.split("/")[0]
        if top in _SOURCE_CATEGORIES:
            cat = top
        chosen.append((cat, path))

    return chosen[:count]


def _load_structures() -> dict:
    """加载曲式模板库（Mubert jingle 方法论：结构模板与素材池解耦）。"""
    tp = os.path.join(_PROJECT_ROOT, "templates", "structures.json")
    try:
        with open(tp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[warn] 曲式模板库加载失败（{e}），使用内置默认", file=sys.stderr)
        return {
            "classic_drop": {
                "min_bars": 13, "fade_out_bars": 2,
                "layers": {"drum": [0, -1], "guita": [0, -1], "bass": [4, -4],
                           "cowbell": [6, -4], "synth": [8, -4]},
            }
        }


def _sha256_file(path: str) -> str | None:
    """文件 sha256（失败返回 None，不抛异常）。"""
    try:
        import hashlib

        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:  # noqa: BLE001
        return None


def engine_fingerprint() -> dict:
    """引擎指纹：任何一处实现漂移都能被日后比对发现（复现失败时先看这里）。"""
    return {
        "remix_version": REMIX_VERSION,
        "main_py_sha256": _sha256_file(os.path.abspath(__file__)),
        "structures_json_sha256": _sha256_file(
            os.path.join(_PROJECT_ROOT, "templates", "structures.json")),
        "mixer_styles_py_sha256": _sha256_file(
            os.path.join(_MUSICKIT_ROOT, "burbidge_album", "mixer_styles.py")),
    }


def _rel_to_root(path: str | None) -> str | None:
    """把绝对路径转成相对 MUSICKIT_ROOT 的 posix 风格相对路径（便于跨机复现）。"""
    if not path:
        return None
    try:
        return os.path.relpath(os.path.abspath(path), _MUSICKIT_ROOT).replace("\\", "/")
    except Exception:  # noqa: BLE001
        return path


def _curve_digest(curve) -> dict | None:
    """逐小节增益曲线太长，落库时存摘要（sha1 + 极值 + 长度）即可精确比对。"""
    if not curve:
        return None
    import hashlib

    vals = [round(float(v), 4) for v in curve]
    return {
        "n": len(vals),
        "sha1": hashlib.sha1(",".join(f"{v:.4f}" for v in vals).encode()).hexdigest()[:16],
        "min": min(vals),
        "max": max(vals),
    }


def build_recipe(*, seed, count, bpm, bars, st_name, st, sections, fade_out_bars,
                 tracks, materials, role_gain, variant_every, style,
                 release_safe, mixer_style, peak_dbfs) -> dict:
    """把「这次到底用了什么」完整落库，供日后精确复现与漂移诊断。

    背景：2026-09-17 重渲历史产物时，早期 genre 流水线的条目虽存了 seed/tracks，
    仍无法复现（与原型包络相关仅 0.09）——配方没记全，事后无从归因。
    自本版起每次渲染都持久化：输入参数 + 实际选曲 + 编排（段落/增益/变体/曲线摘要）
    + 混音师链 + 引擎指纹。
    """
    rec_tracks = []
    for m in materials:
        item = {
            "cat": m.get("cat"),
            "role": m.get("role"),
            "rel": _rel_to_root(m.get("path")),
            "gain_db": (None if m.get("gain_db") is None
                        else round(float(m["gain_db"]), 3)),
        }
        if m.get("start_bar") is not None:
            item["start_bar"], item["end_bar"] = m.get("start_bar"), m.get("end_bar")
        if m.get("accent_every"):
            item["accent_every"] = m.get("accent_every")
        if m.get("variant_every_bars"):
            item["variant_every_bars"] = m.get("variant_every_bars")
        if m.get("seg_b") is not None:
            item["has_variant_b"] = True
        if m.get("gain_curve"):
            item["gain_curve"] = _curve_digest(m.get("gain_curve"))
        rec_tracks.append(item)

    mixer_rec = None
    if style:
        mixer_rec = {
            "slug": style.get("slug"), "name": style.get("name"),
            "target_lufs": style.get("target_lufs"),
            "buses": sorted({_MIXER_ROLE_TO_BUS[m["cat"]]
                             for m in materials if _MIXER_ROLE_TO_BUS.get(m.get("cat"))}),
        }

    return {
        "engine": engine_fingerprint(),
        "inputs": {
            "count": count, "seed": seed, "bpm": bpm, "bars": bars,
            "structure": st_name, "release_safe": bool(release_safe),
            "mixer_style": mixer_style,
            "tracks_arg": sorted(_rel_to_root(p) or "" for _c, p in (tracks or [])) or None,
        },
        "structure": {
            "name": st_name,
            "template": st,
            "sections": {k: list(v) for k, v in (sections or {}).items()},
            "fade_out_bars": fade_out_bars,
        },
        "tracks": rec_tracks,
        "constants": {"role_gain": role_gain, "variant_every": variant_every},
        "mixer": mixer_rec,
        "output": {"peak_dbfs": None if peak_dbfs is None else round(float(peak_dbfs), 3)},
        "recipe_version": 1,
    }


def recipe_digest(recipe: dict) -> str | None:
    """配方摘要（只覆盖影响声音的部分，忽略引擎指纹与输出路径），用于快速比对。"""
    import hashlib

    if not recipe:
        return None
    core = {k: recipe.get(k) for k in
            ("inputs", "structure", "tracks", "constants", "mixer", "recipe_version")}
    return hashlib.sha256(
        json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _resolve_sections(structure: dict, bars: int) -> tuple[dict, int]:
    """按模板与总小节数计算各层 (start_bar, end_bar) 与结尾淡出小节数。"""
    if bars < structure.get("min_bars", 13):
        return {}, 0
    layers = structure.get("layers", {})
    out: dict[str, tuple[int, int]] = {}
    for cat, (s, e) in layers.items():
        if e == -1:                      # -1 = 铺到最后
            end = bars
        elif e < 0:                      # 其余负数 = 距结尾偏移
            end = bars + e
        else:
            end = e
        start = min(s, max(0, end - 1))
        out[cat] = (start, max(start + 1, end))
    return out, int(structure.get("fade_out_bars", 0))


def _intensity_curve(bars: int, start: int, end: int, it: dict) -> list[float]:
    """M4：按模板 intensity 配置生成逐小节增益曲线（进场/退场线性斜坡）。"""
    curve = [0.0] * bars
    if not it:
        return curve
    ramp = max(1, int(it.get("ramp_bars", 1)))
    enter = float(it.get("enter_db", 0.0))
    exit_ = float(it.get("exit_db", 0.0))
    n = max(0, end - start)
    for i in range(min(ramp, n)):          # 进场：enter → 0
        t = (ramp - i) / ramp
        curve[start + i] += enter * t
    for i in range(min(ramp, n)):          # 退场：0 → exit（末小节最深）
        t = (ramp - i) / ramp
        curve[end - 1 - i] += exit_ * t
    return curve


def run_remix(
    count: int = 3,
    seed: int | None = None,
    out_dir: str | None = None,
    fmt: str = "wav",
    bars: int = 32,
    bpm: int | None = None,
    structure: str | None = None,
    tracks: list[tuple[str, str]] | None = None,
    release_safe: bool = False,
    mixer_style: str | None = None,
    key: str | None = None,
    note: str | None = None,
    sample_rate: int | None = None,
    bit_depth: int | None = None,
    bitrate: str | None = None,
    recipe_out: dict | None = None,
) -> str:
    """执行一次 phonk 风格 loop 化混音（F1/F2/F3-v2：切 loop + 变速对齐 + 曲式模板编排）。

    - 每轨素材：整曲(>=4 小节)按能量峰切 1~2 小节 loop；短素材整段使用
    - F3-v2：源 BPM 已知（manifest 路径提示）或可估计（自相关）→ atempo 对齐目标 BPM
    - 编排：曲式模板（--structure，默认随机），不足 min_bars 自动全铺平
    - 混音：分轨 RMS 归一 → overlay 叠加 → 峰值归一 -1.5 dBFS（留编码过冲余量）
    - 输出：默认 32 小节（约 55s@140BPM）
    """
    from core.audio_loader import AudioLoader
    from core.loop_slicer import (
        audio_fingerprint,
        bar_ms,
        build_arrangement,
        duration_ms,
        parse_bpm_hint,
        prepare_material,
        ROLE_ACCENT,
        ROLE_LOOP,
    )
    from utils import make_unique_path

    count = max(1, min(count, 8))
    rng = random.Random(seed)
    # T2-1：目标调性（提示词 scale / CLI --key）。解析失败按「未指定」处理，不做任何偏好。
    _target_key = musical_key.parse_target(key)
    if key and _target_key is None:
        print(f"[remix] 警告：无法解析调性 {key!r}（示例：Cm / Am / F# major / A小调），本次不做调性偏好",
              file=sys.stderr)
    style = style_irs = ms_mod = None
    if mixer_style:
        style, style_irs, ms_mod = _load_mixer_style(mixer_style, rng)
        if style:
            print(f"[remix] 混音师风格：{style['name']}（{style['slug']}）— {style['tagline']}")
    if bpm is None:
        bpm = rng.randint(110, 151)

    # 曲式模板：显式指定或随机选一套（结构模板与素材池解耦，Mubert M1/M3/M5）
    structures = _load_structures()
    if structure and structure in structures:
        st_name = structure
    else:
        st_name = rng.choice(sorted(structures))
    st = structures[st_name]
    desc = st.get("description", "")
    print(f"[remix] 曲式模板：{st_name}" + (f"（{desc}）" if desc else ""))

    # 从各目录 manifest 读取 source 信息（BPM 提示 / 来源溯源 / 授权层级过滤）
    entries_by_cat = _load_pool_manifests(_MUSICKIT_ROOT)
    _cat_manifest: dict[str, dict] = {}
    for pool in entries_by_cat.values():
        _cat_manifest.update(pool)

    if tracks:
        # 手动指定音轨：(category, path) 列表，过滤掉不存在的文件
        chosen: list[tuple[str, str]] = []
        for cat, path in tracks:
            if path and os.path.isfile(path):
                chosen.append((cat, path))
        if not chosen:
            raise FileNotFoundError("手动指定的音轨文件均不存在，请重新选择。")
        # 2026-11-02：原 `--release-safe` 的 tier 过滤已废弃（素材均为公版）
        tracks = chosen
    else:
        tracks = _pick_random_tracks(count, seed, bpm, entries_by_cat, release_safe,
                                     target_key=_target_key)

    # F6：内容指纹去重（同采样只保留一份，跨 mp3/wav 格式）
    fps: dict[str, str] = {}
    deduped: list[tuple[str, str]] = []
    for cat, path in tracks:
        try:
            fp = audio_fingerprint(path)
        except Exception:
            fp = path  # 探测失败则按路径去重
        if fp in fps:
            continue
        fps[fp] = path
        deduped.append((cat, path))
    if len(deduped) < len(tracks):
        print(f"[remix] 内容去重：剔除 {len(tracks) - len(deduped)} 条重复采样")
    tracks = deduped

    print(f"[remix] BPM={bpm}，共 {bars} 小节（{bar_ms(bpm, bars) / 1000:.1f}s），"
          f"已选择 {len(tracks)} 条音轨（phonk 风格）：")
    for i, (cat, path) in enumerate(tracks, 1):
        dur = duration_ms_or(
            path, _manifest_duration_ms(_cat_manifest.get(os.path.basename(path)))
        ) / 1000.0
        print(f"  {i}. [{cat}] {os.path.basename(path)} ({dur:.1f}s)")

    # 段落编排：模板驱动（不足 min_bars 自动全铺平）
    sections, fade_out = _resolve_sections(st, bars)

    # 分轨 RMS 归一目标（dBFS）：叠加后总峰值再归一，避免过载
    ROLE_GAIN = {"drum": -13.0, "bass": -13.0, "guita": -13.0,
                 "cowbell": -19.0, "synth": -15.0,
                 "vocal": -18.0, "sfx": -16.0}
    # A/B 变体切换周期（小节）：旋律层 4 小节换一次，鼓/bass 8 小节换（保持底子稳定）
    VARIANT_EVERY = {"guita": 4, "synth": 4, "bass": 8, "drum": 8, "cowbell": 0,
                     "vocal": 0, "sfx": 0}
    # 同类素材池（B 变体备用源：短素材换同类别文件）
    _cat_files = {}
    for cat in _SOURCE_CATEGORIES:
        _cat_files[cat] = _collect_category_files(os.path.join(_MUSICKIT_ROOT, cat))
    # vocal 角色在随机模式下由 animal 池提供 one-shot 备选
    _cat_files["vocal"] = _cat_files.get("animal", [])

    materials = []
    for cat, path in tracks:
        src_bpm = None
        meta = _cat_manifest.get(os.path.basename(path))
        if meta:
            src_bpm = parse_bpm_hint(meta.get("original_rel", "") or meta.get("original", ""))
        dur = duration_ms_or(path, _manifest_duration_ms(meta))
        # A 变体：曲首区间搜索
        seg = prepare_material(path, bpm, rng, source_bpm=src_bpm,
                               search_start_sec=0.0, search_max_sec=120.0)
        bar = bar_ms(bpm)
        # 短素材（one-shot / 不足 1 小节）→ 点缀层；否则循环层。
        # 骨架层（drum/bass/guita）强制循环层：选音时已保底 >=1 小节 loop，
        # 防止慢速 BPM 下 2~3s 短 loop 被判成点缀、整曲失去律动骨架。
        # sfx（riser/impact）强制点缀，且每 4 小节点缀一次（riser 密集会吵）
        if cat in _SKELETON_CATS:
            role = ROLE_LOOP
        elif cat == "sfx":
            role = ROLE_ACCENT
        else:
            role = ROLE_ACCENT if len(seg) < bar else ROLE_LOOP
        target = ROLE_GAIN.get(cat, -15.0)
        # path 一并存下：配方落库要靠它记录「实际用了哪条素材」（build_recipe 用）
        m = {"role": role, "cat": cat, "seg": seg, "path": path,
             "gain_db": target - seg.dBFS}
        if cat == "sfx":
            m["accent_every"] = 4
        if cat in sections:
            m["start_bar"], m["end_bar"] = sections[cat]
            # M4 段落强度曲线：进场/退场斜坡 + drop 增强（模板 intensity 配置）
            it = st.get("intensity")
            if it:
                s_bar, e_bar = sections[cat]
                curve = _intensity_curve(bars, s_bar, e_bar, it)
                drop_boost = float(it.get("drop_boost_db", 0.0))
                if drop_boost and cat in it.get("drop_layers", []):
                    d_start = int(st.get("intro_bars", 0)) + 1
                    d_end = bars - int(st.get("outro_bars", 0))
                    for b in range(d_start, d_end):
                        if s_bar <= b < e_bar:
                            curve[b] += drop_boost
                if any(curve):
                    m["gain_curve"] = curve

        # B 变体（>12 小节才启用，防单调）：stem 换搜索区间；短素材换同类另一文件
        if bars > 12 and role == ROLE_LOOP:
            if dur >= bar * 4:
                b_path = path
                b_src_bpm = src_bpm
                b_kw = dict(search_start_sec=60.0, search_max_sec=180.0)
            else:
                others = [p for p in _cat_files.get(cat, []) if p != path]
                if not others:
                    m["variant_every_bars"] = 0
                    materials.append(m)
                    continue
                b_path = rng.choice(others)
                b_meta = _cat_manifest.get(os.path.basename(b_path))
                b_src_bpm = (parse_bpm_hint(b_meta.get("original_rel", "") or b_meta.get("original", ""))
                             if b_meta else None)
                b_kw = {}
            try:
                seg_b = prepare_material(b_path, bpm, rng, source_bpm=b_src_bpm, **b_kw)
                if len(seg_b) >= bar:
                    m["seg_b"] = seg_b
                    m["variant_every_bars"] = VARIANT_EVERY.get(cat, 4)
            except Exception:
                pass  # B 变体失败则退化为单素材循环
        materials.append(m)

    # 混音师风格：分轨总线着色（角色 -> 专辑总线映射，跳过电平级，保留引擎编排平衡）
    if style:
        for m in materials:
            bus_key = _MIXER_ROLE_TO_BUS.get(m.get("cat", ""))
            if not bus_key:
                continue
            m["seg"] = _style_segment(m["seg"], style, style_irs, bus_key, ms_mod)
            if m.get("seg_b") is not None:
                m["seg_b"] = _style_segment(m["seg_b"], style, style_irs, bus_key, ms_mod)

    fade_out = int(st.get("fade_out_bars", 0)) if sections else 0
    mix = build_arrangement(materials, bpm, bars, fade_out_bars=fade_out)

    # 混音师风格：母带链（EQ/glue/宽度/饱和/响度目标），峰值按 -1.5 dBFS 留编码余量；
    # 未启用风格时保持原峰值归一化行为
    if style:
        x = _seg_to_np(mix)
        x, _ = ms_mod.master_chain(x, style["master"], ceiling_db=-1.5)
        mix = _np_to_seg(x)
        print(f"[remix] 已应用母带风格链（{style['slug']}，目标 {style['target_lufs']} LUFS）")
    else:
        # 峰值归一化到 -1.5 dBFS（为 mp3/有损编码的过冲留 0.5dB 余量）
        mix = mix.apply_gain(-1.5 - mix.max_dBFS)

    # ---------------------------------------------------------------------
    # 编排配方落库：把本次实际使用的选曲/编排/风格/引擎指纹完整记录，
    # 供日后精确复现与实现漂移归因（详见 build_recipe_docstring）。
    # ---------------------------------------------------------------------
    if recipe_out is not None:
        recipe_out.clear()
        recipe_out.update(build_recipe(
            seed=seed, count=count, bpm=bpm, bars=bars, st_name=st_name, st=st,
            sections=sections, fade_out_bars=fade_out, tracks=tracks,
            materials=materials, role_gain=ROLE_GAIN, variant_every=VARIANT_EVERY,
            style=style, release_safe=release_safe, mixer_style=mixer_style,
            peak_dbfs=mix.max_dBFS,
        ))
        recipe_out["recipe_digest"] = recipe_digest(recipe_out)

    # 交付规格：无损 48k/24bit（默认），有损 48k/16bit + 上限码率
    mix, spec = _apply_delivery_spec(mix, fmt, sample_rate, bit_depth)
    # 导出前后置断言：空/静音/时长异常一律中止，不产生「成功」的坏文件
    _validate_mix(mix, bpm, bars)
    _bitrate = bitrate or LOSSY_BITRATE.get((fmt or "").lower())
    if out_dir is None:
        out_dir = os.path.join(_PROJECT_ROOT, "output")
    # 同秒冲突自动递增（_1/_2），杜绝两次快速运行互相覆盖
    output_path = make_unique_path(out_dir, "phonk_remix", "", fmt)
    AudioLoader.export(mix, output_path, fmt=fmt, bitrate=_bitrate,
                       codec=spec["codec"], parameters=spec["parameters"])
    # 导出后断言：文件存在、非空、可回读且时长合理
    _verify_exported(output_path, bpm, bars)

    # sentence 落盘：把提示词的整句写进 ID3 comment，成品自带「怎么做的」痕迹
    _tag_result = None
    if note:
        from core.tagging import write_tags

        _tag_result = write_tags(
            output_path,
            title=os.path.splitext(os.path.basename(output_path))[0],
            artist="musickit",
            album=(style["slug"] if style else None),
            comment=note,
        )
        if _tag_result["ok"]:
            print(f"[remix] 已写入元数据：{', '.join(_tag_result['written'])}")
        else:
            print(f"[remix] 警告：元数据写入失败（不影响成品）：{_tag_result['error']}",
                  file=sys.stderr)

    print(f"[remix] 交付规格：{fmt.upper()} {spec['sample_rate']}Hz / {spec['bit_depth']}bit / "
          f"{spec['channels']}ch ≈ {spec['kbps']:.0f} kbps"
          + (f"（码率 {_bitrate}）" if _bitrate else ""))
    if recipe_out is not None:
        recipe_out["output"].update({
            "path": output_path, "fmt": fmt,
            "sample_rate": spec["sample_rate"], "bit_depth": spec["bit_depth"],
            "codec": spec["codec"],
            "duration_ms": int(duration_ms(output_path)),
            "note": note,
            "tags": (_tag_result or {}).get("written"),
        })

    print(f"[remix] 混音完成（{len(mix) / 1000:.1f}s，{bpm}BPM x {bars} 小节），"
          f"已保存至：\n  {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="musickit 专属版混音器（已去除视频合成）",
    )
    parser.add_argument(
        "--remix", action="store_true",
        help="命令行模式：从 bass/drum/guita 随机选音混音（phonk 风格）",
    )
    parser.add_argument(
        "--count", type=_positive_int, default=3,
        help="混音音轨数（默认 3：drum+bass+guita 最小骨架；典型 phonk 4~6）",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="随机种子，固定可复现选择",
    )
    parser.add_argument(
        "--bars", type=_positive_int, default=32,
        help="输出小节数（默认 32，约 55s@140BPM；>12 小节自动编排 intro→drop→outro 段落）",
    )
    parser.add_argument(
        "--bpm", type=_bpm_int, default=None,
        help="混音速度 BPM（默认随机 110~150）",
    )
    parser.add_argument(
        "--structure", type=str, default=None,
        help="曲式模板（templates/structures.json，如 classic_drop/ambient_ghost/loop_stack；默认随机）",
    )
    parser.add_argument(
        "--out", type=str, default=None,
        help="输出目录（默认 remix/output）",
    )
    parser.add_argument(
        "--format", type=str, default="wav", choices=["wav", "mp3", "ogg", "flac"],
        help="输出格式（默认 wav）",
    )
    parser.add_argument(
        "--release-safe", action="store_true",
        help="【已废弃】素材均为公共领域，本开关不再做任何过滤（保留以兼容旧脚本）",
    )
    parser.add_argument(
        "--note", type=str, default=None, metavar="TEXT",
        help="写入成品 ID3 comment 的文本（提示词驱动路径自动传 sentence，便于事后追溯）",
    )
    parser.add_argument(
        "--key", type=str, default=None, metavar="KEY",
        help="目标调性（如 Cm / Am / F# major / A小调）：优先选用同调/关系调/五度关系素材；"
             "解析失败则不做偏好。素材调性由 remix/tools/detect_keys.py 预先标注",
    )
    parser.add_argument(
        "--mixer-style", type=str, default=None,
        help="混音师风格着色（burbidge/ghenea/clearmountain/marroquin/pensado/blake/"
             "lordalge/schmitt/mikedean/stent/random；默认不启用，保持原 phonk 处理链）",
    )
    parser.add_argument("--tasks", action="store_true", help="审计任务事件日志（<输出目录>/pipeline.log）")
    parser.add_argument("--limit", type=int, default=100, help="--tasks 显示条数")
    parser.add_argument("--json", action="store_true", help="--tasks JSON 输出")
    args = parser.parse_args()

    if args.tasks:
        from pipelog import PipelineLog
        _out = args.out or os.path.join(_PROJECT_ROOT, "output")
        _log_path = os.path.join(_out, "pipeline.log")
        if not os.path.isfile(_log_path):
            print(f"[tasks] 无任务日志: {_log_path}")
            return
        _entries = PipelineLog(_log_path).read(limit=args.limit)
        if args.json:
            print(json.dumps(_entries, ensure_ascii=False, indent=2))
            return
        print(f"任务日志 {_log_path}（最近 {len(_entries)} 条）：")
        for _e in _entries:
            _extra = " ".join(f"{k}={v}" for k, v in _e.items()
                              if k not in ("seq", "ts", "type", "stage", "run_id"))
            print(f"  #{_e['seq']} {_e['ts']} [{_e['type']}] {_extra}")
        _runs = sorted({_e.get("run_id") for _e in _entries if _e.get("run_id")})
        _errs = [_e for _e in _entries if _e["type"] == "stage_error"]
        print(f"  涉及运行 {len(_runs)} 次，阶段错误 {len(_errs)} 条")
        return

    if args.remix:
        # ── 任务事件日志（日志即事实源，<输出目录>/pipeline.log） ──
        from pipelog import PipelineLog
        _out_dir = args.out or os.path.join(_PROJECT_ROOT, "output")
        tasklog = PipelineLog(os.path.join(_out_dir, "pipeline.log"))
        run_id = PipelineLog.new_run_id()
        tasklog.append("run_start", run_id=run_id, count=args.count, seed=args.seed,
                       bars=args.bars, bpm=args.bpm, structure=args.structure,
                       release_safe=args.release_safe, mixer_style=args.mixer_style)
        try:
            result = run_remix(count=args.count, seed=args.seed, out_dir=args.out,
                               fmt=args.format, bars=args.bars, bpm=args.bpm,
                               structure=args.structure, release_safe=args.release_safe,
                               mixer_style=args.mixer_style, key=args.key,
                               note=args.note)
        except MixValidationError as _exc:
            tasklog.append("stage_error", stage="remix", run_id=run_id, error=str(_exc)[:300])
            tasklog.append("run_end", run_id=run_id, ok=False, errors=1)
            print(f"[remix] 错误：{_exc}", file=sys.stderr)
            raise SystemExit(2)
        except Exception as _exc:
            tasklog.append("stage_error", stage="remix", run_id=run_id, error=str(_exc)[:300])
            tasklog.append("run_end", run_id=run_id, ok=False, errors=1)
            raise
        tasklog.append("stage_done", stage="remix", run_id=run_id, output=str(result))
        tasklog.append("run_end", run_id=run_id, ok=True, errors=0)
        return

    # 默认启动图形界面
    import tkinter as tk
    from gui.main_window import MixerApp

    root = tk.Tk()
    MixerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
