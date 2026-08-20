"""Phase 2 步骤 3：归一化入库。
把 candidates.json 中的候选采样转成 44.1kHz / 立体声 / 16bit wav：
  - 首尾静音修剪（-45dB 阈值，留 50ms padding）
  - 峰值归一化到 -3 dBFS
  - 按 synth (N).wav 从 51 起续号写入 G:\\music\\musickit\\synth\\
  - 内容哈希去重（同内容不重复入库）
  - 写入 synth/manifest.json（编号 → 来源包 → 原文件名 → 授权 → 时长）
用法: python ingest_synth.py [--limit N] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

# pydub 需要 ffmpeg 在 PATH
_BIN = r"G:\music\musickit\remix\bin"
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
from pydub import AudioSegment  # noqa: E402
from pydub.silence import detect_leading_silence  # noqa: E402

SYNTH_DIR = r"G:\music\musickit\synth"
DOWNLOADS = r"G:\music\musickit\archived\downloads"
MANIFEST_PATH = os.path.join(SYNTH_DIR, "manifest.json")
START_NUM = 51          # 从 51 起续号（1~50 为旧占位，将被移入 archived）
MAX_FILES = 200         # 入库上限
PAD_MS = 50
SILENCE_THRESH = -45.0  # dB
TARGET_PEAK = -3.0      # dBFS

# 来源包 → 授权（MusicRadar SampleRadar 条款：royalty-free，勿转售样本包本身）
PACK_LICENSE = {
    "EBM": {"license": "Royalty-free (MusicRadar SampleRadar)", "url": "https://www.musicradar.com/music-tech/samples/sampleradar-205-free-ebm-samples"},
    "deep_house": {"license": "Royalty-free (MusicRadar SampleRadar)", "url": "https://www.musicradar.com/music-tech/samples/sampleradar-267-free-deep-house-samples"},
    "funk_keys": {"license": "Royalty-free (MusicRadar SampleRadar)", "url": "https://www.musicradar.com/music-tech/samples/sampleradar-273-free-funk-keys-samples"},
    "hiphop90s": {"license": "Royalty-free (MusicRadar SampleRadar)", "url": "https://www.musicradar.com/music-tech/samples/want-to-recreate-the-classic-sound-of-golden-age-90s-hip-hop-download-this-pack-of-537-free-samples-from-sampleradar"},
}


def detect_pack(rel):
    for key in PACK_LICENSE:
        if rel.startswith(key + "/") or ("/" + key + "/") in rel:
            return key
    # 兜底：从路径第一段推断
    first = rel.split("/")[0].lower().replace("-", "_")
    for key in PACK_LICENSE:
        if key.lower().replace("-", "_") in first:
            return key
    return "unknown"


def content_hash(data: bytes):
    return hashlib.sha256(data).hexdigest()


def load_existing_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def next_number(manifest):
    nums = [int(re.search(r"\((\d+)\)", e["file"]).group(1)) for e in manifest["entries"]
            if re.search(r"\((\d+)\)", e["file"])]
    # 也扫描目录里的现有文件号，避免撞名
    for name in os.listdir(SYNTH_DIR):
        m = re.search(r"synth \((\d+)\)\.wav", name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else START_NUM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=MAX_FILES)
    ap.add_argument("--per-pack", type=int, default=50,
                    help="每个来源包最多入库数（均衡分配，默认 50）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cand_path = os.path.join(DOWNLOADS, "candidates.json")
    if not os.path.exists(cand_path):
        print(f"未找到 {cand_path}，请先运行 audit_pack.py", file=sys.stderr)
        sys.exit(1)
    with open(cand_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)["candidates"]

    # 按包均衡取数：每包按路径排序取前 per_pack 个，再按包顺序拼接
    by_pack = {}
    for c in candidates:
        by_pack.setdefault(detect_pack(c["rel"]), []).append(c)
    balanced = []
    for pack in sorted(by_pack):
        balanced.extend(by_pack[pack][:args.per_pack])
    candidates = balanced
    print(f"均衡取数：{ {p: min(len(v), args.per_pack) for p, v in by_pack.items()} }")

    manifest = load_existing_manifest()
    num = next_number(manifest)
    seen = set(e.get("sha256") for e in manifest["entries"])
    ingested = 0
    skipped_dup = 0
    failed = 0

    for c in candidates:
        if ingested >= args.limit:
            break
        src = c["path"]
        if not os.path.exists(src):
            continue
        try:
            seg = AudioSegment.from_file(src)
            seg = seg.set_channels(2).set_frame_rate(44100).set_sample_width(2)
            # 首尾静音修剪（pydub.silence 函数形式，兼容所有版本）
            lead = detect_leading_silence(seg, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[lead:]
            rev = seg.reverse()
            trail = detect_leading_silence(rev, silence_threshold=SILENCE_THRESH, chunk_size=10)
            seg = seg[:len(seg) - trail]
            if len(seg) < 300:
                skipped_dup += 1
                continue
            # 峰值归一化到 -3 dBFS
            delta = TARGET_PEAK - seg.max_dBFS
            seg = seg.apply_gain(delta)
            raw = seg.raw_data
            h = content_hash(raw)
            if h in seen:
                skipped_dup += 1
                continue
            seen.add(h)
            out_name = f"synth ({num}).wav"
            out_path = os.path.join(SYNTH_DIR, out_name)
            if args.dry_run:
                print(f"[dry-run] {src} → {out_name}  ({seg.duration_seconds:.2f}s)")
            else:
                seg.export(out_path, format="wav")
            entry = {
                "file": out_name,
                "source_pack": detect_pack(c["rel"]),
                "original": c["name"],
                "original_rel": c["rel"],
                "license": PACK_LICENSE.get(detect_pack(c["rel"]), {}).get("license", "unknown"),
                "duration_s": round(seg.duration_seconds, 2),
                "sha256": h,
            }
            manifest["entries"].append(entry)
            num += 1
            ingested += 1
        except Exception as e:
            failed += 1
            print(f"[fail] {src}: {e}", file=sys.stderr)

    manifest["generated"] = datetime.now().isoformat(timespec="seconds")
    print(f"入库 {ingested} 个；去重/过短跳过 {skipped_dup}；失败 {failed}；"
          f"synth 目录当前共 {len(manifest['entries'])} 个真实采样（编号起 51）")
    if not args.dry_run:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"manifest 已写入 {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
