"""Phase 2 扩展：把 downloads 里剩余音频按类别全部入库。

分类路由（按文件名/路径关键词，注意先用鼓类匹配，避免 "bassdrum" 误入 bass）：
  drum/beat → G:\\music\\musickit\\drum\\     （编号从现有最大+1 续）
  bass      → G:\\music\\musickit\\bass\\     （同上）
  synth/keys/其他 → G:\\music\\musickit\\synth\\（同上，含 fx/未匹配，作纹理层）

处理：44.1kHz 立体声 16bit、首尾静音修剪、峰值归一 -3dBFS、sha256 去重、
      时长过滤（bass/synth 0.3~8s，drum 0.3~16s，容纳 4 小节慢速 loop）。
跳过：已入库的 199 个（synth/manifest.json 中记录）。
manifest：各目录写入/追加 manifest.json。
用法: python ingest_categories.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

_BIN = str(_MK_ROOT / "remix" / "bin")
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
from pydub import AudioSegment  # noqa: E402
from pydub.silence import detect_leading_silence  # noqa: E402
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

DOWNLOADS = str(_MK_ROOT / "archived" / "downloads")
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff")
SILENCE_THRESH = -45.0
TARGET_PEAK = -3.0

CATS = {
    "drum": {
        "dir": str(_MK_ROOT / "drum"),
        "pat": re.compile(r"(beat|drum|kick|snare|hat|tom|cym|perc|clap|shaker)", re.I),
        "max_ms": 16000,
        "min_ms": 100,   # 鼓 one-shot（kick/hat）常短于 300ms
    },
    "bass": {
        "dir": str(_MK_ROOT / "bass"),
        "pat": re.compile(r"(bass|808)", re.I),
        "max_ms": 12000,  # 4 小节慢速 bass loop
        "min_ms": 300,
    },
    "synth": {
        "dir": str(_MK_ROOT / "synth"),
        "pat": re.compile(r"__never__"),
        "max_ms": 8000,
        "min_ms": 300,
    },
}
PACK_LICENSE = {
    "EBM": "Royalty-free (MusicRadar SampleRadar)",
    "deep_house": "Royalty-free (MusicRadar SampleRadar)",
    "funk_keys": "Royalty-free (MusicRadar SampleRadar)",
    "hiphop90s": "Royalty-free (MusicRadar SampleRadar)",
}


def detect_pack(rel):
    first = rel.split("\\")[0].split("/")[0].lower().replace("-", "_")
    for k in PACK_LICENSE:
        if k.lower().replace("-", "_") in first or first in k.lower().replace("-", "_"):
            return k
    return "unknown"


def route(rel, fn):
    """返回 'drum' / 'bass' / 'synth'。"""
    hay = rel.replace("\\", "/") + "/" + fn
    if CATS["drum"]["pat"].search(hay):
        return "drum"
    if CATS["bass"]["pat"].search(hay):
        return "bass"
    return "synth"


def load_manifest(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def save_manifest(path, m):
    m["generated"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


def max_number(cat_dir, prefix):
    best = 0
    for name in os.listdir(cat_dir):
        m = re.search(re.escape(prefix) + r" \((\d+)\)\.wav", name)
        if m:
            best = max(best, int(m.group(1)))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="每类上限（0=不限）")
    args = ap.parse_args()

    # 已入库 skip 集（synth 的 199 个，避免重复入库到其它类别）
    sm = load_manifest(os.path.join(CATS["synth"]["dir"], "manifest.json"))
    skip = set()
    for e in sm["entries"]:
        rel = e.get("original_rel", "")
        p = os.path.normpath(os.path.join(DOWNLOADS, rel, e.get("original", "")))
        skip.add(p.lower())

    manifests = {c: load_manifest(os.path.join(v["dir"], "manifest.json")) for c, v in CATS.items()}
    nums = {c: max_number(v["dir"], c) + 1 for c, v in CATS.items()}
    seen = {}
    for c in CATS:
        seen[c] = set(e.get("sha256") for e in manifests[c]["entries"])

    stats = {c: {"ok": 0, "dup": 0, "skip": 0, "fail": 0, "dur_filter": 0} for c in CATS}
    files = []
    for dp, _dns, fns in os.walk(DOWNLOADS):
        for fn in fns:
            if not fn.lower().endswith(AUDIO_EXT):
                continue
            files.append((dp, fn))
    files.sort(key=lambda x: (x[0], x[1]))
    print(f"共扫描音频 {len(files)} 个（skip 集 {len(skip)} 个）")

    for dp, fn in files:
        fp = os.path.join(dp, fn)
        rel = os.path.relpath(dp, DOWNLOADS)
        if fp.lower() in skip:
            stats["synth"]["skip"] += 1
            continue
        cat = route(rel, fn)
        s = stats[cat]
        if args.limit and stats[cat]["ok"] >= args.limit:
            continue
        try:
            seg = AudioSegment.from_file(fp)
            seg = seg.set_channels(2).set_frame_rate(44100).set_sample_width(2)
            if not (CATS[cat]["min_ms"] <= len(seg) <= CATS[cat]["max_ms"]):
                s["dur_filter"] += 1
                continue
            lead = detect_leading_silence(seg, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[lead:]
            rev = seg.reverse()
            trail = detect_leading_silence(rev, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[:len(seg) - trail]
            if len(seg) < CATS[cat]["min_ms"] or seg.dBFS < SILENCE_THRESH:
                s["dur_filter"] += 1
                continue
            delta = TARGET_PEAK - seg.max_dBFS
            seg = seg.apply_gain(delta)
            h = hashlib.sha256(seg.raw_data).hexdigest()
            if h in seen[cat]:
                s["dup"] += 1
                continue
            seen[cat].add(h)
            n = nums[cat]
            out_name = f"{cat} ({n}).wav"
            out_path = os.path.join(CATS[cat]["dir"], out_name)
            if not args.dry_run:
                seg.export(out_path, format="wav")
            manifests[cat]["entries"].append({
                "file": out_name,
                "source_pack": detect_pack(rel),
                "original": fn,
                "original_rel": rel.replace("\\", "/"),
                "license": PACK_LICENSE.get(detect_pack(rel), "unknown"),
                "duration_s": round(seg.duration_seconds, 2),
                "sha256": h,
            })
            nums[cat] += 1
            s["ok"] += 1
        except Exception as e:
            s["fail"] += 1
            if s["fail"] <= 5:
                print(f"[fail] {fp}: {e}", file=sys.stderr)

    for c, v in CATS.items():
        print(f"[{c}] 新增 {stats[c]['ok']}（跳过已入库 {stats[c]['skip']}、去重 {stats[c]['dup']}、"
              f"时长/静音过滤 {stats[c]['dur_filter']}、失败 {stats[c]['fail']}）→ "
              f"{v['dir']} 现共 {len(manifests[c]['entries'])} 条 manifest")
        if not args.dry_run:
            save_manifest(os.path.join(v["dir"], "manifest.json"), manifests[c])


if __name__ == "__main__":
    main()
