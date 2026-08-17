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
import sys

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


def _pick_random_tracks(count: int, seed: int | None) -> list[tuple[str, str]]:
    """按 phonk 风格随机挑选音轨。

    Returns:
        [(category, path), ...] 列表，长度 = count。
        优先保证 phonk 骨架 drum / bass / guita 各至少 1 条，
        其次尽量补入牛铃(cowbell)与 synth/采样这两类 phonk 标志层，
        剩余数量从全部素材随机补足（允许同类重复）。
    """
    rng = random.Random(seed)

    by_cat: dict[str, list[str]] = {}
    all_files: list[str] = []
    for cat in _RANDOM_POOLS:
        files = _collect_category_files(os.path.join(_MUSICKIT_ROOT, cat))
        by_cat[cat] = files
        all_files.extend(files)

    if not all_files:
        raise FileNotFoundError(
            f"在 {_MUSICKIT_ROOT} 下未找到任何音频素材"
            f"（请确认 bass / drum / guita / cowbell / synth 目录中存在音频文件）。"
        )

    chosen: list[tuple[str, str]] = []

    # 1) 优先凑出 phonk 最小骨架（drum + bass + guita 各 1 条）
    for cat in _PHONK_SKELETON:
        files = by_cat[cat]
        if files:
            chosen.append((cat, rng.choice(files)))

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
) -> str:
    """执行一次 phonk 风格 loop 化混音（F1/F2/F3-v2：切 loop + 变速对齐 + 曲式模板编排）。

    - 每轨素材：整曲(>=4 小节)按能量峰切 1~2 小节 loop；短素材整段使用
    - F3-v2：源 BPM 已知（manifest 路径提示）或可估计（自相关）→ atempo 对齐目标 BPM
    - 编排：曲式模板（--structure，默认随机），不足 min_bars 自动全铺平
    - 混音：分轨 RMS 归一 → overlay 叠加 → 峰值归一 -1 dBFS
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
    from utils import generate_output_name

    count = max(1, min(count, 8))
    rng = random.Random(seed)
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

    # 从各目录 manifest 读取 source 信息（BPM 提示 / 来源溯源）
    _cat_manifest = {}
    for cat in _SOURCE_CATEGORIES:
        mp = os.path.join(_MUSICKIT_ROOT, cat, "manifest.json")
        try:
            with open(mp, "r", encoding="utf-8") as f:
                for e in json.load(f).get("entries", []):
                    _cat_manifest[e["file"]] = e
        except Exception:
            pass

    if tracks:
        # 手动指定音轨：(category, path) 列表，过滤掉不存在的文件
        chosen: list[tuple[str, str]] = []
        for cat, path in tracks:
            if path and os.path.isfile(path):
                chosen.append((cat, path))
        if not chosen:
            raise FileNotFoundError("手动指定的音轨文件均不存在，请重新选择。")
        tracks = chosen
    else:
        tracks = _pick_random_tracks(count, seed)

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
        # sfx（riser/impact）强制点缀，且每 4 小节点缀一次（riser 密集会吵）
        if cat == "sfx":
            role = ROLE_ACCENT
        else:
            role = ROLE_ACCENT if len(seg) < bar else ROLE_LOOP
        target = ROLE_GAIN.get(cat, -15.0)
        m = {"role": role, "seg": seg, "gain_db": target - seg.dBFS}
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

    fade_out = int(st.get("fade_out_bars", 0)) if sections else 0
    mix = build_arrangement(materials, bpm, bars, fade_out_bars=fade_out)

    # 峰值归一化到 -1 dBFS
    mix = mix.apply_gain(-1.0 - mix.max_dBFS)

    if out_dir is None:
        out_dir = os.path.join(_PROJECT_ROOT, "output")
    output_path = os.path.join(out_dir, generate_output_name("phonk_remix", "", fmt))
    AudioLoader.export(mix, output_path, fmt=fmt)

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
    args = parser.parse_args()

    if args.remix:
        run_remix(count=args.count, seed=args.seed, out_dir=args.out,
                  fmt=args.format, bars=args.bars, bpm=args.bpm,
                  structure=args.structure)
        return

    # 默认启动图形界面
    import tkinter as tk
    from gui.main_window import MixerApp

    root = tk.Tk()
    MixerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
