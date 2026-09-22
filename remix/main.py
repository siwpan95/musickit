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
# pydub 使用项目内置 ffmpeg / ffprobe（bin/ 目录，零外部依赖）
# 必须在 import pydub 之前把 bin/ 加入 PATH，否则 import 时 pydub 找不到
# ffmpeg 会发出 RuntimeWarning。
# =========================================================================
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_BIN_DIR = os.path.join(_PROJECT_ROOT, "bin")
os.environ["PATH"] = _BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import pydub  # noqa: E402

_BUNDLED_FFMPEG = os.path.join(_BIN_DIR, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
_BUNDLED_FFPROBE = os.path.join(_BIN_DIR, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")

pydub.AudioSegment.converter = _BUNDLED_FFMPEG
pydub.AudioSegment.ffprobe = _BUNDLED_FFPROBE

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

from core.loop_slicer import bar_ms, duration_ms  # noqa: E402


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
    cat: str,
    entries: dict[str, dict[str, dict]],
    dropped: list[tuple[str, int]],
) -> list[str]:
    """--release-safe 过滤：只保留 license_tier 为 free/pack 的素材。

    manifest 无记录或 tier 缺失/unknown/restricted 的文件一律剔除，
    剔除数量追加到 dropped（[(类别, 剔除数)]）。
    """
    pool = entries.get(cat, {})
    kept: list[str] = []
    for path in files:
        e = pool.get(os.path.basename(path))
        tier = (e or {}).get("license_tier")
        if tier in _RELEASE_SAFE_TIERS:
            kept.append(path)
    n = len(files) - len(kept)
    if n:
        dropped.append((cat, n))
    return kept


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
    for cat in _RANDOM_POOLS:
        files = _collect_category_files(os.path.join(_MUSICKIT_ROOT, cat))
        if release_safe:
            files = _filter_release_safe(files, cat, entries, dropped)
        by_cat[cat] = files
        all_files.extend(files)

    if release_safe and dropped:
        print("[remix] --release-safe：已剔除受限/未知授权素材 "
              + "、".join(f"{c} {n}" for c, n in dropped), file=sys.stderr)

    if not all_files:
        raise FileNotFoundError(
            f"在 {_MUSICKIT_ROOT} 下未找到任何音频素材"
            f"（请确认 bass / drum / guita / cowbell / synth 目录中存在音频文件）。"
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
        if release_safe:
            before = len(chosen)
            chosen = [
                (cat, path) for cat, path in chosen
                if (entries_by_cat.get(cat, {}).get(os.path.basename(path)) or {}).get("license_tier")
                in _RELEASE_SAFE_TIERS
            ]
            if len(chosen) < before:
                print(f"[remix] --release-safe：剔除 {before - len(chosen)} 条受限/未知授权音轨",
                      file=sys.stderr)
        tracks = chosen
    else:
        tracks = _pick_random_tracks(count, seed, bpm, entries_by_cat, release_safe)

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
        dur = duration_ms(path) / 1000.0
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
        dur = duration_ms(path)
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
    _bitrate = bitrate or LOSSY_BITRATE.get((fmt or "").lower())
    if out_dir is None:
        out_dir = os.path.join(_PROJECT_ROOT, "output")
    # 同秒冲突自动递增（_1/_2），杜绝两次快速运行互相覆盖
    output_path = make_unique_path(out_dir, "phonk_remix", "", fmt)
    AudioLoader.export(mix, output_path, fmt=fmt, bitrate=_bitrate,
                       codec=spec["codec"], parameters=spec["parameters"])

    print(f"[remix] 交付规格：{fmt.upper()} {spec['sample_rate']}Hz / {spec['bit_depth']}bit / "
          f"{spec['channels']}ch ≈ {spec['kbps']:.0f} kbps"
          + (f"（码率 {_bitrate}）" if _bitrate else ""))
    if recipe_out is not None:
        recipe_out["output"].update({
            "path": output_path, "fmt": fmt,
            "sample_rate": spec["sample_rate"], "bit_depth": spec["bit_depth"],
            "codec": spec["codec"],
            "duration_ms": int(duration_ms(output_path)),
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
        "--count", type=int, default=3,
        help="混音音轨数（默认 3：drum+bass+guita 最小骨架；典型 phonk 4~6）",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="随机种子，固定可复现选择",
    )
    parser.add_argument(
        "--bars", type=int, default=32,
        help="输出小节数（默认 32，约 55s@140BPM；>12 小节自动编排 intro→drop→outro 段落）",
    )
    parser.add_argument(
        "--bpm", type=int, default=None,
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
        help="发布安全模式：仅使用授权层级为 free/pack 的素材（restricted/unknown 一律剔除）",
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
                               mixer_style=args.mixer_style)
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
