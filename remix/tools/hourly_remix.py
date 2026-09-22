"""
hourly_remix.py — 每小时「随机风格」混音驱动（musickit remix 流水线，面向网易云发布）

设计取舍（按用户反馈 2026-09-16）
-------------------------------
* 主路径 = remix 自带的随机混音（``main.py --remix``）：phonk 风格随机选曲 + 随机 BPM
  + 随机曲式模板，**这就是"随机风格"的本意**，不引入提示词驱动的复杂链路。
* 进阶路径（可选 ``--fusion``）：走 music 提示词链 + **跨类融合**（``music_prompt_generator
  --fusion``，随机混搭两类、乐器/情绪去重），再用 prompt_driven_remix 映射成素材轨。
* 混音师染色（``--mixer-style``，默认 none）：24 位之一，random 随机；只影响音色/响度，
  不影响选曲——作为叠加层，不喧宾夺主。
* **默认关闭发布安全（--release-safe off）**：全素材池参与，避免内容过于单调；
  ``--release-safe`` 显式开启时只用 license_tier ∈ {free, pack}（restricted/unknown 剔除）。

交付规格（2026-09-17 起生效，面向网易云音乐）
--------------------------------------------
平台要求：**码率 > 320 kbps、采样率 > 44.1 kHz、单文件 < 200 MB**。
有损编码的上限就是 mp3 320 kbps，永远达不到「> 320 kbps」，因此对外交付一律无损。

    默认：WAV / 48 kHz / 24 bit / 立体声 = 2304 kbps，120s ≈ 34.6 MB ✅

每次导出后用项目内置 ffprobe 回读实测值（codec / sample_rate / bit_depth / kbps /
size），写入 ``hourly_index.json`` 的 ``delivery`` 字段并给出 ``delivery_ok``：
只有当 码率>320kbps 且 采样率>44100Hz 且 体积<max-size-mb 且 时长在容差内时才为 true。

时长控制
--------
    bars = round(target_sec * bpm / 240)      # 4 拍/小节
BPM 取偶数 -> bars = bpm/2，理论时长精确 120.0s（实测偏差 <0.1s）。

产物
----
    remix/output/hourly/<时间戳>_remix_<bpm>bpm_<bars>bars_<结构>[_<mixer>].wav
    （--fusion 模式为 _fusion_<风格>_...；--format 可切 mp3/ogg/flac）
同目录维护 hourly_index.json（逐首元数据 + 时长/交付规格校验）、playlist.m3u8、hourly_remix.log。

用法（Windows / F:\\Python314）
------------------------------
    F:\\Python314\\python.exe tools\\hourly_remix.py                       # 随机风格 x 2 分钟（全素材池）
    F:\\Python314\\python.exe tools\\hourly_remix.py --mixer-style random   # 叠加随机混音师染色
    F:\\Python314\\python.exe tools\\hourly_remix.py --fusion               # 走提示词跨类融合（进阶）
    F:\\Python314\\python.exe tools\\hourly_remix.py --count 5 --bpm 140    # 固定 5 轨 / 140BPM
    F:\\Python314\\python.exe tools\\hourly_remix.py --seed 42              # 可复现
    F:\\Python314\\python.exe tools\\hourly_remix.py --dry-run              # 只打印本次随机结果
    F:\\Python314\\python.exe tools\\hourly_remix.py --release-safe         # 开启授权过滤（仅发布安全时）
    F:\\Python314\\python.exe tools\\hourly_remix.py --sample-rate 96000 --bit-depth 24  # 更高交付规格
    F:\\Python314\\python.exe tools\\hourly_remix.py --format mp3 --bitrate 320k        # 有损兜底
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import sys
import time
import traceback

# Windows 控制台编码：TTY 下不动代码页（避免 GBK 控制台打中文乱码），
# 重定向/管道（自动化环境）时强制 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        if _s.isatty():
            _s.reconfigure(errors="replace")
        else:
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSICKIT_ROOT = os.path.dirname(REMIX_DIR)

# 本目录加入 sys.path（本机设了 PYTHONSAFEPATH=1，脚本目录不会自动加入）
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import audio_fingerprint  # noqa: E402
MUSIC_DIR = os.path.join(MUSICKIT_ROOT, "music")
DEFAULT_OUT = os.path.join(REMIX_DIR, "output", "hourly")
INDEX_NAME = "hourly_index.json"
LOG_NAME = "hourly_remix.log"
PLAYLIST_NAME = "playlist.m3u8"


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------
def log(msg: str, log_path: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def _load_module(name: str, path: str):
    """按文件路径加载模块（避免同名模块冲突 / 包导入问题）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_stack():
    """加载 remix main 引擎 +（fusion 用）music 提示词链路。

    返回 (remix_main, pdr_or_None, mpg_or_None)；fusion 未启用时后两者为 None。
    """
    for p in (MUSIC_DIR, REMIX_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)
    remix_main = _load_module("musickit_remix_main", os.path.join(REMIX_DIR, "main.py"))
    pdr = mpg = None
    if getattr(args_pass, "fusion", False):  # 延迟判断是否加载重链路
        pdr = _load_module("musickit_prompt_driven_remix",
                           os.path.join(MUSIC_DIR, "prompt_driven_remix.py"))
        mpg = _load_module("musickit_music_prompt_generator",
                           os.path.join(MUSIC_DIR, "music_prompt_generator.py"))
    return remix_main, pdr, mpg


def read_index(index_path: str) -> list[dict]:
    if not os.path.isfile(index_path):
        return []
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def write_index(index_path: str, entries: list[dict]) -> None:
    tmp = index_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, index_path)


def write_playlist(index_path: str, entries: list[dict]) -> None:
    p = os.path.join(os.path.dirname(index_path), PLAYLIST_NAME)
    lines = ["#EXTM3U"]
    for e in entries:
        path = e.get("path") or ""
        if not path or not os.path.isfile(path):
            continue
        dur = int(float(e.get("duration_s") or 0))
        title = (f"{e.get('genre_label') or e.get('mode', '?')} · {e.get('bpm', '?')}BPM · "
                 f"{e.get('mixer_style') or 'no-mixer'} · {e.get('created', '')}")
        lines.append(f"#EXTINF:{dur},{title}")
        lines.append(path.replace("\\", "/"))
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def recent_values(entries: list[dict], key: str, window: int) -> set[str]:
    if window <= 0:
        return set()
    return {str(e.get(key)) for e in entries[-window:] if e.get(key)}


def pick_excluding(rng: random.Random, pool: list[str], exclude: set[str]) -> str | None:
    if not pool:
        return None
    fresh = [x for x in pool if x not in exclude]
    return rng.choice(fresh or pool)


def mixer_slugs() -> list[str]:
    bp = os.path.join(MUSICKIT_ROOT, "burbidge_album")
    if bp not in sys.path:
        sys.path.insert(0, bp)
    try:
        import mixer_styles as ms
        return list(ms.SLUGS)
    except Exception:  # noqa: BLE001
        return []


def even_bpm(rng: random.Random, lo: int, hi: int) -> int:
    """[lo,hi] 内取一个偶数 BPM（偶数 -> 时长可精确到 0.1s 内）。"""
    lo, hi = max(70, lo), min(200, hi)
    if lo % 2:
        lo += 1
    if lo > hi:
        return max(70, hi - (hi % 2 == 1))
    return rng.randrange(lo, hi + 1, 2)


def bars_for(target_sec: float, bpm: int) -> int:
    return max(4, int(round(target_sec * bpm / 240.0)))


def probe_delivery(path: str, ffprobe: str) -> dict:
    """用 ffprobe 回读导出文件的真实交付规格（不看脚本自述，只看实测）。"""
    import subprocess

    info: dict = {}
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_name,sample_rate,channels,bits_per_raw_sample,bits_per_sample:"
             "format=duration,size,bit_rate",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(r.stdout or "{}")
        st = (data.get("streams") or [{}])[0]
        fm = data.get("format") or {}
        sr = int(st.get("sample_rate") or 0)
        depth = int(st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0)
        ch = int(st.get("channels") or 0)
        bit_rate = int(fm.get("bit_rate") or 0)
        # 容器头缺失 bit_rate 时用 PCM 公式反推（采样率 x 位深 x 声道）
        if not bit_rate and sr and depth and ch:
            bit_rate = sr * depth * ch
        size_mb = round(int(fm.get("size") or 0) / 1048576, 2)
        info = {
            "codec": st.get("codec_name") or "",
            "sample_rate": sr,
            "bit_depth": depth,
            "channels": ch,
            "kbps": round(bit_rate / 1000.0, 1),
            "size_mb": size_mb,
            "ffprobe_duration_s": round(float(fm.get("duration") or 0), 3),
        }
    except Exception as exc:  # noqa: BLE001
        info = {"probe_error": str(exc)}
    return info


def judge_delivery(info: dict, target_sec: float, tolerance: float,
                   max_size_mb: float) -> tuple[bool, list[str]]:
    """按发布要求判定交付是否合规，返回 (是否合规, 不合规原因列表)。"""
    reasons: list[str] = []
    kbps = float(info.get("kbps") or 0)
    sr = int(info.get("sample_rate") or 0)
    size_mb = float(info.get("size_mb") or 0)
    dur = float(info.get("ffprobe_duration_s") or 0)
    if kbps <= 320:
        reasons.append(f"码率 {kbps}kbps ≤ 320kbps")
    if sr <= 44100:
        reasons.append(f"采样率 {sr}Hz ≤ 44100Hz")
    if size_mb <= 0:
        reasons.append("体积读取失败")
    elif size_mb >= max_size_mb:
        reasons.append(f"体积 {size_mb}MB ≥ {max_size_mb}MB 上限")
    if dur and abs(dur - target_sec) > tolerance:
        reasons.append(f"时长 {dur}s 偏离目标 {target_sec}s 超过 {tolerance}s")
    if info.get("probe_error"):
        reasons.append(f"ffprobe 失败：{info['probe_error']}")
    return (not reasons), reasons


# 全局引用（load_stack 用到），在 main() 里赋值
args_pass: argparse.Namespace | None = None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    global args_pass
    ap = argparse.ArgumentParser(description="每小时随机风格混音（musickit remix）")
    ap.add_argument("--fusion", action="store_true",
                    help="进阶：走 music 提示词链 + 跨类融合（随机混搭两类）")
    ap.add_argument("--count", type=int, default=5, help="音轨数（默认 5，remix 骨架 3~8）")
    ap.add_argument("--bpm-min", type=int, default=110, help="BPM 下限（默认 110）")
    ap.add_argument("--bpm-max", type=int, default=150, help="BPM 上限（默认 150）")
    ap.add_argument("--bpm", type=int, default=None, help="固定 BPM（覆盖随机）")
    ap.add_argument("--mixer-style", type=str, default="none",
                    help="混音师染色：none(默认)/random/具体 slug（如 mikedean）")
    ap.add_argument("--target-sec", type=float, default=120.0,
                    help="目标时长（秒，默认 120＝两分钟）")
    ap.add_argument("--format", type=str, default="wav", choices=["wav", "mp3", "ogg", "flac"],
                    help="输出格式（默认 wav：发布要求码率>320kbps，有损上限 320k 达不到）")
    ap.add_argument("--sample-rate", type=int, default=None,
                    help=f"交付采样率 Hz（默认 {48000}，>44100 才合规）")
    ap.add_argument("--bit-depth", type=int, default=None,
                    help="无损位深 bit（默认 24；有损格式强制 16）")
    ap.add_argument("--bitrate", type=str, default=None,
                    help="有损码率（默认按格式上限：mp3/ogg/aac 320k）")
    ap.add_argument("--max-size-mb", type=float, default=200.0,
                    help="单文件大小上限 MB（默认 200，与平台要求一致）")
    ap.add_argument("--out", type=str, default=DEFAULT_OUT, help=f"输出目录（默认 {DEFAULT_OUT}）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（固定可复现）")
    ap.add_argument("--no-repeat", type=int, default=3,
                    help="风格/曲式/混音师避开最近 N 次用过的（默认 3，0=不避）")
    ap.add_argument("--attempts", type=int, default=3, help="失败重试次数（默认 3）")
    ap.add_argument("--tolerance", type=float, default=3.0, help="时长容差秒（默认 3）")
    ap.add_argument("--release-safe", action=argparse.BooleanOptionalAction, default=False,
                    help="发布安全模式（默认关）：仅用 license_tier=free/pack 的素材；"
                         "--no-release-safe 关闭（默认，内容更丰富）")
    ap.add_argument("--mix-only", action="store_true", help="不写索引/播放列表（只产音频）")
    ap.add_argument("--dry-run", action="store_true", help="只打印本次随机结果，不混音")
    ap.add_argument("--list-mixers", action="store_true", help="列出 24 位混音师 slug 后退出")
    args = ap.parse_args()
    args_pass = args

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, LOG_NAME)
    index_path = os.path.join(args.out, INDEX_NAME)

    if args.list_mixers:
        for s in mixer_slugs():
            print(s)
        return 0

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 2**31 - 1)
    rng = random.Random(seed)
    remix_main, pdr, mpg = load_stack()

    entries = [] if args.mix_only else read_index(index_path)
    used_structs = recent_values(entries, "structure", args.no_repeat)
    used_mixers = recent_values(entries, "mixer_style", args.no_repeat)

    # 1) BPM（偶数化保证时长精确）
    bpm = args.bpm if args.bpm else even_bpm(rng, args.bpm_min, args.bpm_max)
    bars = bars_for(args.target_sec, bpm)

    # 2) 曲式模板（remix 自带，随机选一套，避开最近）
    structures = sorted(remix_main._load_structures().keys())
    structure = pick_excluding(rng, structures, used_structs)

    # 3) 混音师染色（可选叠加）
    mixer = args.mixer_style
    if mixer and mixer.lower() == "none":
        mixer = None
    elif mixer and mixer.lower() == "random":
        slugs = mixer_slugs()
        mixer = pick_excluding(rng, slugs, used_mixers)

    mode = "fusion" if args.fusion else "remix"
    # 4) fusion 进阶：提示词跨类融合 -> 具体素材轨
    tracks = None
    genre_label = None
    gaps = []
    if args.fusion and pdr is not None:
        prompts = mpg.batch_generate(1, fusion=True, seed=seed)
        prompt = prompts[0]
        # 偶数化 BPM 后让映射层用我们选定的速度
        prompt["bpm"] = f"{bpm} BPM"
        mp = pdr.prompt_to_mix_params(prompt, rng, max_tracks=args.count,
                                      add_skeleton=True, release_safe=args.release_safe)
        bpm = int(mp.get("bpm") or bpm)
        bars = bars_for(args.target_sec, bpm)
        structure = mp.get("structure") or structure
        tracks = mp.get("tracks") or []
        gaps = mp.get("gaps") or []
        genre_label = prompt.get("label", "")
        # 旋律层兜底
        MELODIC = {"guita", "synth", "keys", "strings", "brass", "woodwind", "ethnic", "cowbell"}
        if not ({c for c, _ in tracks} & MELODIC):
            files = pdr.collect_for_pool("guita")
            if args.release_safe:
                files = pdr._m_filter_release_safe(files, "guita",
                                                  pdr._pool_entries(), [])
            files = pdr._loop_preferring(files, pdr._pool_entries().get("guita"))
            if files:
                p = pdr.pick_loop_candidate(files, bpm, rng, pdr._pool_entries().get("guita"))
                if p:
                    tracks.append(("guita", p))

    _lossless = args.format in remix_main.LOSSLESS_FORMATS
    spec_sr = args.sample_rate or remix_main.DELIVERY_SPEC["sample_rate"]
    spec_depth = ((args.bit_depth or remix_main.DELIVERY_SPEC["bit_depth"])
                  if _lossless else 16)
    expect_sec = bars * 4 * 60.0 / bpm
    plan = dict(seed=seed, mode=mode, bpm=bpm, bars=bars,
                expect_sec=round(expect_sec, 2), structure=structure,
                mixer_style=mixer, count=args.count, fmt=args.format,
                sample_rate=spec_sr, bit_depth=spec_depth,
                release_safe=bool(args.release_safe), out=args.out)
    if tracks is not None:
        plan["genre"] = genre_label
        plan["n_tracks"] = len(tracks)
        plan["gaps"] = gaps
    log(f"计划：{json.dumps(plan, ensure_ascii=False)}", log_path)
    if tracks is not None:
        for i, (cat, path) in enumerate(tracks, 1):
            log(f"  轨 {i}. [{cat}] {os.path.basename(path)}", log_path)
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if tracks is not None and not tracks:
        log("无可用音轨（可能授权过滤后池为空），终止", log_path)
        print("FAILED: no tracks", file=sys.stderr)
        return 1

    last_err = None
    for attempt in range(1, max(1, args.attempts) + 1):
        try_seed = seed if attempt == 1 else seed + attempt * 7919
        t0 = time.time()
        try:
            recipe: dict = {}
            raw = remix_main.run_remix(
                count=args.count, seed=try_seed, out_dir=args.out, fmt=args.format,
                bars=bars, bpm=bpm, structure=structure, tracks=tracks,
                release_safe=args.release_safe, mixer_style=mixer,
                sample_rate=args.sample_rate, bit_depth=args.bit_depth,
                bitrate=args.bitrate, recipe_out=recipe,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log(f"第 {attempt} 次失败：{exc}", log_path)
            log(traceback.format_exc(limit=3).strip().replace("\n", " | "), log_path)
            continue

        elapsed = time.time() - t0
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}_{mode}_{bpm}bpm_{bars}bars_{structure}" + (f"_{mixer}" if mixer else "")
        final = os.path.join(args.out, f"{base}.{args.format}")
        n = 1
        while os.path.exists(final):
            final = os.path.join(args.out, f"{base}_{n}.{args.format}")
            n += 1
        shutil.move(raw, final)

        dur_s = round(remix_main.duration_ms(final) / 1000.0, 2)
        size_mb = round(os.path.getsize(final) / 1048576, 2)
        delta = round(dur_s - args.target_sec, 2)
        ok = abs(delta) <= args.tolerance
        log(f"完成：{os.path.basename(final)} | {dur_s}s（目标 {args.target_sec}s，"
            f"偏差 {delta:+.2f}s{' OK' if ok else ' WARN 超容差'}）| {size_mb}MB | "
            f"耗时 {elapsed:.1f}s | 第 {attempt} 次尝试", log_path)

        # 交付规格回读（ffprobe 实测，不信任自述参数）
        ffprobe_bin = os.path.join(REMIX_DIR, "bin",
                                   "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
        info = probe_delivery(final, ffprobe_bin)
        d_ok, d_reasons = judge_delivery(info, args.target_sec, args.tolerance,
                                         args.max_size_mb)
        log(f"交付规格：{info.get('codec','?')} {info.get('sample_rate','?')}Hz/"
            f"{info.get('bit_depth','?')}bit/{info.get('channels','?')}ch "
            f"≈ {info.get('kbps','?')}kbps | {info.get('size_mb','?')}MB | "
            f"{'合规 ✅' if d_ok else '不合规 ❌ ' + '; '.join(d_reasons)}", log_path)

        # 内容指纹（跨编码稳定）：日后重渲可用它证明「还是原来那一首」
        try:
            fp = audio_fingerprint.fingerprint(final)
        except Exception as exc:  # noqa: BLE001
            fp = {"error": str(exc)}

        if not args.mix_only:
            entries = read_index(index_path)
            rec = dict(
                created=time.strftime("%Y-%m-%d %H:%M:%S"),
                file=os.path.basename(final), path=final,
                duration_s=dur_s, size_mb=size_mb, duration_ok=ok,
                mode=mode, bpm=bpm, bars=bars, structure=structure, mixer_style=mixer,
                seed=try_seed, fmt=args.format, sample_rate=spec_sr,
                bit_depth=spec_depth,
                bitrate=(args.bitrate or remix_main.LOSSY_BITRATE.get(args.format)),
                release_safe=bool(args.release_safe), elapsed_s=round(elapsed, 1),
                attempt=attempt,
                delivery=info, delivery_ok=d_ok,
                recipe=recipe, fingerprints=fp,
            )
            if tracks is not None:
                rec["genre"] = genre_label
                rec["tracks"] = [f"{c}:{os.path.basename(p)}" for c, p in tracks]
                rec["gaps"] = gaps
            entries.append(rec)
            write_index(index_path, entries)
            write_playlist(index_path, entries)
            log(f"索引已更新：{len(entries)} 首（{index_path}）", log_path)
        print(f"OUTPUT={final}")
        print(f"DELIVERY={'OK' if d_ok else 'FAIL'} codec={info.get('codec')} "
              f"sr={info.get('sample_rate')} depth={info.get('bit_depth')} "
              f"ch={info.get('channels')} kbps={info.get('kbps')} "
              f"size_mb={info.get('size_mb')}")
        if not d_ok:
            print(f"DELIVERY_FAIL_REASONS={'; '.join(d_reasons)}", file=sys.stderr)
        return 0

    log(f"全部 {args.attempts} 次尝试均失败：{last_err}", log_path)
    print(f"FAILED: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
