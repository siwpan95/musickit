"""Phase 4.5：真吉他采样入库（补 guita 层的真实吉他音轨）。

从 candidates.json 中筛出吉他相关文件（guitar/gtr/riff/chug/wah/fuzz，
排除 bass），归一化后以 guita (N).wav 从现有最大编号+1 续写入 G:\\musickit\\guita\\，
manifest 写入/合并 G:\\musickit\\guita\\manifest.json。
用法: python ingest_guitar.py [--limit N] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

_BIN = r"G:\musickit\remix\bin"
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
from pydub import AudioSegment  # noqa: E402
from pydub.silence import detect_leading_silence  # noqa: E402

GUITA_DIR = r"G:\musickit\guita"
DOWNLOADS = r"G:\musickit\archived\downloads"
MANIFEST_PATH = os.path.join(GUITA_DIR, "manifest.json")
GTR_PAT = re.compile(r"(guitar|gtr|riff|chug|wah|fuzz|guit)", re.I)
BASS_PAT = re.compile(r"bass", re.I)
SILENCE_THRESH = -45.0
TARGET_PEAK = -3.0
MAX_MS = 16000
MIN_MS = 300

PACK_LICENSE = {
    "guitar_bass272": "Royalty-free (MusicRadar SampleRadar)",
    "processed_guitar188": "Royalty-free (MusicRadar SampleRadar)",
}


def detect_pack(rel):
    first = rel.split("\\")[0].split("/")[0].lower().replace("-", "_")
    for k in PACK_LICENSE:
        if k.lower().replace("-", "_") in first or first in k.lower().replace("-", "_"):
            return k
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cand_path = os.path.join(DOWNLOADS, "candidates.json")
    with open(cand_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)["candidates"]

    guitar = [c for c in candidates
              if GTR_PAT.search(c["rel"] + "/" + c["name"]) and not BASS_PAT.search(c["name"])]
    print(f"吉他候选 {len(guitar)} 个（{len(candidates)} 总候选）")
    if args.limit:
        guitar = guitar[:args.limit]

    # 现有 manifest 与编号
    manifest = {"generated": None, "entries": []}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    best = 0
    for name in os.listdir(GUITA_DIR):
        m = re.search(r"guita \((\d+)\)\.wav", name)
        if m:
            best = max(best, int(m.group(1)))
    seen = set(e.get("sha256") for e in manifest["entries"])

    num = best + 1
    ok = dup = fail = 0
    for c in guitar:
        try:
            seg = AudioSegment.from_file(c["path"])
            seg = seg.set_channels(2).set_frame_rate(44100).set_sample_width(2)
            if not (MIN_MS <= len(seg) <= MAX_MS):
                continue
            lead = detect_leading_silence(seg, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[lead:]
            rev = seg.reverse()
            trail = detect_leading_silence(rev, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[:len(seg) - trail]
            if len(seg) < MIN_MS or seg.dBFS < SILENCE_THRESH:
                continue
            seg = seg.apply_gain(TARGET_PEAK - seg.max_dBFS)
            h = hashlib.sha256(seg.raw_data).hexdigest()
            if h in seen:
                dup += 1
                continue
            seen.add(h)
            out_name = f"guita ({num}).wav"
            if not args.dry_run:
                seg.export(os.path.join(GUITA_DIR, out_name), format="wav")
            manifest["entries"].append({
                "file": out_name,
                "source_pack": detect_pack(c["rel"]),
                "original": c["name"],
                "original_rel": c["rel"].replace("\\", "/"),
                "license": PACK_LICENSE.get(detect_pack(c["rel"]), "unknown"),
                "duration_s": round(seg.duration_seconds, 2),
                "sha256": h,
            })
            num += 1
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"[fail] {c['path']}: {e}", file=sys.stderr)

    manifest["generated"] = datetime.now().isoformat(timespec="seconds")
    print(f"入库 {ok} 个；去重 {dup}；失败 {fail}；guita 现有 manifest 条目 "
          f"{len(manifest['entries'])}（真吉他 + 之前流水线入库）")
    if not args.dry_run:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"manifest 已写入 {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
