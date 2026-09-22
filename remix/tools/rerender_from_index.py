"""rerender_from_index.py — 用索引里记录的参数「复现」历史混音为发布级无损 WAV。

背景
----
`hourly_remix.py` 的历史产物是 128 kbps mp3，**不满足网易云要求**（码率 > 320 kbps、
采样率 > 44.1 kHz、< 200 MB），且 mp3 → wav 只能得到「假无损」（内容已不可逆丢失）。
唯一正确的补救是用 `hourly_index.json` 里已存的 `seed / bpm / bars / structure /
mixer_style`（+ `release_safe`、`tracks`）**重新渲染**。

与 hourly_remix 的区别
----------------------
* 不做任何随机：`structure` / `mixer_style` / `bpm` / `bars` 全部取自索引，
  不再经过 `pick_excluding` 随机层，因此**逐条可复现**。
* 若索引条目带 `tracks`（早期流水线会记录具体素材轨），则按轨复现（保真度更高）。
* 渲染后做两项独立核验：
  1. ffprobe 实测交付规格（codec / 采样率 / 位深 / 实测码率 / 体积）；
  2. 与原产物做**包络相关性**比对（解码为 8 kHz 单声道后算 Pearson r），
     用客观数字证明「重渲 == 原曲」，而不是"看起来一样"。
* 增量写 `release_index.json`，支持 `--resume` 断点续跑。

用法（Windows / F:\\Python314）
------------------------------
    F:\\Python314\\python.exe tools\\rerender_from_index.py --dry-run        # 只列计划
    F:\\Python314\\python.exe tools\\rerender_from_index.py --limit 1        # 先试 1 首
    F:\\Python314\\python.exe tools\\rerender_from_index.py                  # 全量（默认续跑）
    F:\\Python314\\python.exe tools\\rerender_from_index.py --only-seed 949014691
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

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
MUSIC_DIR = os.path.join(MUSICKIT_ROOT, "music")
DEFAULT_SOURCE_INDEX = os.path.join(REMIX_DIR, "output", "hourly", "hourly_index.json")
DEFAULT_OUT = os.path.join(REMIX_DIR, "output", "release")
RELEASE_INDEX = "release_index.json"
RERENDER_LOG = "rerender.log"

# 本目录加入 sys.path（本机设了 PYTHONSAFEPATH=1，脚本目录不会自动加入）
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import audio_fingerprint  # noqa: E402

FFPROBE = os.path.join(REMIX_DIR, "bin", "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
FFMPEG = os.path.join(REMIX_DIR, "bin", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")

# 交付规格（与 main.py DELIVERY_SPEC 保持一致）
SR = 48000
DEPTH = 24
MAX_SIZE_MB = 200.0
ENVELOPE_SR = 8000  # 保真比对用的降采样率


def log(msg: str, path: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def load_remix_main():
    for p in (MUSIC_DIR, REMIX_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(
        "musickit_remix_main_rr", os.path.join(REMIX_DIR, "main.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["musickit_remix_main_rr"] = mod
    spec.loader.exec_module(mod)
    return mod


def read_json(path: str, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def write_json_atomic(path: str, data, backup_if_shrink_from: int | None = None) -> None:
    """原子写；若条目数比 `backup_if_shrink_from` 少，先留一份 .bak 再写。

    教训（2026-09-17 22:58）：`--no-resume` 曾把 release_index.json 里其余记录清空，
    28 条实测数据被覆盖（靠 rerender.log 与磁盘文件才得以重建）。此后写入一律带收缩保护。
    """
    if backup_if_shrink_from is not None and len(data) < backup_if_shrink_from:
        try:
            if os.path.isfile(path):
                shutil.copy2(path, path + ".bak")
        except Exception:  # noqa: BLE001
            pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def find_original(path_hint: str, base_dir: str) -> str | None:
    """索引里的 path 可能因外部整理而失效 → 按文件名递归回找。"""
    if path_hint and os.path.isfile(path_hint):
        return path_hint
    if not path_hint:
        return None
    name = os.path.basename(path_hint)
    for root, _dirs, files in os.walk(base_dir):
        if name in files:
            return os.path.join(root, name)
    return None


def envelope(path: str):
    """解码为 8 kHz 单声道 10 ms RMS 包络（复用共享指纹模块，跨编码可比）。"""
    return audio_fingerprint.envelope(path, sr=ENVELOPE_SR)


def envelope_corr(a_path: str, b_path: str) -> float | None:
    """两条音频的包络 Pearson 相关系数（1.0 = 内容一致）。"""
    return audio_fingerprint.envelope_corr(envelope(a_path), envelope(b_path))


def probe(path: str) -> dict:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries",
             "stream=codec_name,sample_rate,channels,bits_per_raw_sample,bits_per_sample:"
             "format=duration,size,bit_rate",
             "-of", "json", path],
            capture_output=True, text=True, timeout=120,
        )
        d = json.loads(r.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        fm = d.get("format") or {}
        sr = int(st.get("sample_rate") or 0)
        depth = int(st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0)
        ch = int(st.get("channels") or 0)
        br = int(fm.get("bit_rate") or 0) or (sr * depth * ch)
        return {
            "codec": st.get("codec_name") or "",
            "sample_rate": sr, "bit_depth": depth, "channels": ch,
            "kbps": round(br / 1000.0, 1),
            "size_mb": round(int(fm.get("size") or 0) / 1048576, 2),
            "ffprobe_duration_s": round(float(fm.get("duration") or 0), 3),
        }
    except Exception as exc:  # noqa: BLE001
        return {"probe_error": str(exc)}


def resolve_tracks(entry: dict) -> list[tuple[str, str]] | None:
    """解析「当时实际用了哪些素材」。

    优先用 `recipe.tracks`（新格式，含相对路径，最精确）；回退到旧的
    `tracks` 字符串列表（`cat:basename`）；两者都没有则返回 None（交给 seed 随机）。
    任一轨找不到则返回 None，并在日志中说明（宁可退回随机也不要错配素材）。
    """
    rec = (entry.get("recipe") or {}).get("tracks")
    if rec:
        out: list[tuple[str, str]] = []
        for item in rec:
            rel = item.get("rel")
            cat = item.get("cat")
            if not rel or not cat:
                return None
            p = os.path.normpath(os.path.join(MUSICKIT_ROOT, rel))
            if not os.path.isfile(p):
                return None
            out.append((cat, p))
        return out or None

    raw = entry.get("tracks")
    if not raw:
        return None
    out2: list[tuple[str, str]] = []
    for item in raw:
        if ":" not in item:
            return None
        cat, name = item.split(":", 1)
        cat_dir = os.path.join(MUSICKIT_ROOT, cat)
        hit = None
        for root, _dirs, files in os.walk(cat_dir):
            if name in files:
                hit = os.path.join(root, name)
                break
        if not hit:
            return None
        out2.append((cat, hit))
    return out2 or None


def compare_recipes(old: dict, new: dict) -> dict:
    """逐层比对新旧配方，定位「哪一层变了」——比只给一个 bool 有用得多。"""
    if not old or not new:
        return {"available": False}
    res: dict = {"available": True}
    res["engine_same"] = old.get("engine") == new.get("engine")
    res["recipe_digest_same"] = old.get("recipe_digest") == new.get("recipe_digest")

    ot, nt = old.get("tracks") or [], new.get("tracks") or []
    o_rel = [t.get("rel") for t in ot]
    n_rel = [t.get("rel") for t in nt]
    # rel 缺失时不能判定为「相同」——那只是两边都空，属假通过
    res["selection_incomplete"] = (not o_rel) or (not n_rel) or \
                                  any(r is None for r in (o_rel + n_rel))
    res["selection_match"] = (not res["selection_incomplete"]) and o_rel == n_rel
    res["selection_old"] = o_rel
    res["selection_new"] = n_rel

    def _arr(t):
        return [(x.get("cat"), x.get("start_bar"), x.get("end_bar"),
                 x.get("variant_every_bars"), x.get("accent_every"),
                 (x.get("gain_curve") or {}).get("sha1")) for x in t]
    res["arrangement_match"] = _arr(ot) == _arr(nt)

    og = [t.get("gain_db") for t in ot]
    ng = [t.get("gain_db") for t in nt]
    res["gain_match"] = (len(og) == len(ng) and all(
        (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 0.02)
        for a, b in zip(og, ng)))

    res["structure_match"] = (old.get("structure") or {}).get("sections") == \
                             (new.get("structure") or {}).get("sections")
    res["mixer_match"] = old.get("mixer") == new.get("mixer")
    res["constants_match"] = old.get("constants") == new.get("constants")
    res["inputs_match"] = old.get("inputs") == new.get("inputs")
    return res


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
            except Exception:  # noqa: BLE001
                pass
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    global SR, DEPTH
    ap = argparse.ArgumentParser(description="从索引复现历史混音为发布级 WAV")
    ap.add_argument("--source-index", default=DEFAULT_SOURCE_INDEX, help="来源索引（hourly_index.json）")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"输出目录（默认 {DEFAULT_OUT}）")
    ap.add_argument("--format", default="wav", choices=["wav", "flac", "mp3"])
    ap.add_argument("--sample-rate", type=int, default=SR)
    ap.add_argument("--bit-depth", type=int, default=DEPTH)
    ap.add_argument("--only-seed", type=int, default=None, help="只重渲指定 seed")
    ap.add_argument("--limit", type=int, default=0, help="只重渲前 N 首（0=全部）")
    ap.add_argument("--no-resume", action="store_true", help="忽略已有结果，全部重渲")
    ap.add_argument("--no-fidelity", action="store_true", help="跳过与原产物的包络比对")
    ap.add_argument("--backfill-fingerprints", action="store_true",
                    help="只给既有产物补记内容指纹（不渲染）")
    ap.add_argument("--dry-run", action="store_true", help="只列计划不渲染")
    args = ap.parse_args()

    SR, DEPTH = args.sample_rate, args.bit_depth
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, RERENDER_LOG)
    rel_index_path = os.path.join(args.out, RELEASE_INDEX)
    src_base = os.path.dirname(os.path.abspath(args.source_index))

    src = read_json(args.source_index, [])
    if not src:
        print(f"FAILED: 来源索引为空或不可读：{args.source_index}", file=sys.stderr)
        return 1
    todo = [e for e in src if (e.get("fmt") or "mp3").lower() != args.format]
    excluded = [e.get("file") for e in todo if e.get("excluded_from_release")]
    if excluded:
        # 已判定无法复现/不纳入发布的条目不允许被重新唤起（需手动清掉该标记）
        todo = [e for e in todo if not e.get("excluded_from_release")]
    if args.only_seed is not None:
        todo = [e for e in todo if e.get("seed") == args.only_seed]
    if args.limit:
        todo = todo[:args.limit]

    missing = [e.get("file") for e in todo
               if any(e.get(k) in (None, "") for k in ("seed", "bpm", "bars", "structure"))]
    if missing:
        log(f"⚠️ {len(missing)} 条缺少 seed/bpm/bars/structure，将跳过：{missing[:3]}", log_path)
        todo = [e for e in todo if e.get("file") not in missing]

    log(f"计划：{len(todo)} 首 → {args.out}（{args.format} {SR}Hz/{DEPTH}bit）", log_path)
    if excluded:
        log(f"跳过 {len(excluded)} 条已标记 excluded_from_release 的条目", log_path)

    if args.dry_run:
        for i, e in enumerate(todo, 1):
            tr = f" tracks={len(e['tracks'])}" if e.get("tracks") else ""
            print(f"{i:2d}. seed={e['seed']:<12} {e['bpm']:>3}BPM/{e['bars']:>2}bars "
                  f"{e['structure']:<14} mixer={e.get('mixer_style')}{tr}  ← {e.get('file')}")
        return 0

    if args.backfill_fingerprints:
        # 对已存在的产物补记内容指纹（不渲染）：日后重渲可直接比对，无需再依赖原文件
        existing = read_json(rel_index_path, [])
        n = 0
        for e in existing:
            p = e.get("path") or ""
            if not os.path.isfile(p):
                continue
            e["fingerprints"] = audio_fingerprint.fingerprint(p)
            n += 1
        write_json_atomic(rel_index_path, existing, backup_if_shrink_from=len(existing))
        log(f"已为 {n} 条既有产物补记内容指纹（envelope_hash / sha256 / size）", log_path)
        print(f"BACKFILL_DONE n={n} index={rel_index_path}")
        return 0

    remix_main = load_remix_main()
    all_records = read_json(rel_index_path, [])
    prev_by_source = {d.get("source_file"): d for d in all_records if d.get("source_file")}
    # 已有记录**始终**保留：--no-resume 只表示"不跳过已存在的产物"，不清空索引
    done = list(all_records)
    base_count = len(all_records)
    done_stems = {d.get("source_file") for d in done}

    ok_n = skip_n = fail_n = 0
    for i, e in enumerate(todo, 1):
        src_file = e.get("file") or ""
        stem = os.path.splitext(src_file)[0]
        target = os.path.join(args.out, f"{stem}.{args.format}")
        if (not args.no_resume) and src_file in done_stems and os.path.isfile(target):
            skip_n += 1
            log(f"[{i}/{len(todo)}] 跳过（已存在）：{os.path.basename(target)}", log_path)
            continue

        tracks = resolve_tracks(e)
        params = dict(
            count=int(e.get("count") or 5), seed=int(e["seed"]), out_dir=args.out,
            fmt=args.format, bars=int(e["bars"]), bpm=int(e["bpm"]),
            structure=e["structure"], tracks=tracks,
            release_safe=bool(e.get("release_safe")), mixer_style=e.get("mixer_style"),
            sample_rate=SR, bit_depth=DEPTH,
        )
        tag = (f"[{i}/{len(todo)}] seed={params['seed']} {params['bpm']}BPM/"
               f"{params['bars']}bars {params['structure']} mixer={params['mixer_style']}"
               + (f" tracks={len(tracks)}" if tracks else ""))
        log(f"{tag} 开始渲染…", log_path)

        t0 = time.time()
        buf = io.StringIO()
        recipe: dict = {}
        try:
            with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
                raw = remix_main.run_remix(recipe_out=recipe, **params)
        except Exception as exc:  # noqa: BLE001
            fail_n += 1
            log(f"{tag} ❌ 渲染失败：{exc}", log_path)
            log("  " + traceback.format_exc(limit=3).strip().replace("\n", " | "), log_path)
            continue

        elapsed = round(time.time() - t0, 1)
        if os.path.abspath(raw) != os.path.abspath(target):
            shutil.move(raw, target)
        info = probe(target)
        d_ok = (info.get("kbps", 0) > 320 and info.get("sample_rate", 0) > 44100
                and 0 < info.get("size_mb", 0) < MAX_SIZE_MB
                and abs(info.get("ffprobe_duration_s", 0) - 120.0) <= 3.0)

        orig = find_original(e.get("path"), src_base)
        corr = None if (args.no_fidelity or not orig) else envelope_corr(target, orig)
        chk = compare_recipes(e.get("recipe") or {}, recipe)
        fp_new = audio_fingerprint.fingerprint(target)
        # 回归判据：与「上一版已核验产物」的内容指纹比对（比与原 mp3 比对更可靠）
        prev = prev_by_source.get(src_file) or {}
        prev_fp = (prev.get("fingerprints") or {}).get("envelope_hash")
        src_fp = (e.get("fingerprints") or {}).get("envelope_hash")

        rec = {
            "source_file": src_file, "source_path": e.get("path"),
            "original_found": orig, "file": os.path.basename(target), "path": target,
            "seed": params["seed"], "bpm": params["bpm"], "bars": params["bars"],
            "structure": params["structure"], "mixer_style": params["mixer_style"],
            "count": params["count"], "release_safe": params["release_safe"],
            "tracks": e.get("tracks"), "fmt": args.format,
            "duration_s": info.get("ffprobe_duration_s"), "size_mb": info.get("size_mb"),
            "duration_ok": abs(info.get("ffprobe_duration_s", 0) - 120.0) <= 3.0,
            "delivery": info, "delivery_ok": d_ok,
            "fidelity_corr": None if corr is None else round(corr, 5),
            "recipe": recipe, "recipe_check": chk,
            "fingerprints": fp_new,
            "source_envelope_hash": src_fp,
            "prev_release_envelope_hash": prev_fp,
            "elapsed_s": elapsed, "rendered": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if prev_fp and fp_new.get("envelope_hash"):
            rec["fingerprint_match"] = prev_fp == fp_new["envelope_hash"]
        if src_fp and fp_new.get("envelope_hash"):
            rec["fingerprint_match_source"] = src_fp == fp_new["envelope_hash"]
        # reproduced：优先看与原产物的内容相关性；没有原文件时退化为"与上一版已核验产物一致"
        if corr is not None:
            rec["reproduced"] = bool(corr >= 0.99)
        elif rec.get("fingerprint_match"):
            rec["reproduced"] = True
        else:
            rec["reproduced"] = None  # 无从判定，不假装通过
        done = [d for d in done if d.get("source_file") != src_file] + [rec]
        write_json_atomic(rel_index_path, done, backup_if_shrink_from=base_count)

        drift = ""
        if chk.get("available"):
            drift = (" | 配方: 选曲%s 编排%s 增益%s 结构%s 混音师%s 常量%s 引擎%s"
                     % ("=" if chk["selection_match"] else "≠",
                        "=" if chk["arrangement_match"] else "≠",
                        "=" if chk["gain_match"] else "≠",
                        "=" if chk["structure_match"] else "≠",
                        "=" if chk["mixer_match"] else "≠",
                        "=" if chk["constants_match"] else "≠",
                        "=" if chk["engine_same"] else "≠"))
        status = "✅" if d_ok else "❌"
        fp_txt = (" | 指纹%s" % ("=" if rec["fingerprint_match"] else "≠")
                  if "fingerprint_match" in rec else "")
        log(f"{tag} {status} {os.path.basename(target)} | {info.get('codec')} "
            f"{info.get('sample_rate')}Hz/{info.get('bit_depth')}bit {info.get('kbps')}kbps "
            f"{info.get('size_mb')}MB | 保真r={rec['fidelity_corr']}{drift}{fp_txt} | {elapsed}s",
            log_path)
        ok_n += 1

    log(f"本轮结束：成功 {ok_n} / 跳过 {skip_n} / 失败 {fail_n}（索引 {rel_index_path}）", log_path)
    print(f"RERENDER_DONE ok={ok_n} skip={skip_n} fail={fail_n} out={args.out}")
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
