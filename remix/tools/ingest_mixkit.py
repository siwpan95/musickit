"""Mixkit 音效入库：动物叫声 → animal/、riser/impact/transition → sfx/。

归一化（44.1k 立体声 16bit、修剪静音、峰值 -3dBFS、sha256 去重）后编号入库，
manifest 记录来源与授权（Mixkit License：个人/商用免费，勿转售音效本体）。
用法: python ingest_mixkit.py [--dry-run]
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

DOWNLOADS = r"G:\musickit\archived\downloads"
TARGETS = {
    "mixkit_animals": {"dir": r"G:\musickit\animal", "prefix": "animal"},
    "mixkit_sfx": {"dir": r"G:\musickit\sfx", "prefix": "sfx"},
}
LICENSE = "Mixkit License (personal/commercial free; do not redistribute the SFX as-is)"
SILENCE_THRESH = -45.0
TARGET_PEAK = -3.0
MAX_MS = 16000
MIN_MS = 100


def load_manifest(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def max_number(cat_dir, prefix):
    best = 0
    if os.path.isdir(cat_dir):
        for name in os.listdir(cat_dir):
            m = re.search(re.escape(prefix) + r" \((\d+)\)\.wav", name)
            if m:
                best = max(best, int(m.group(1)))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for sub, cfg in TARGETS.items():
        src_dir = os.path.join(DOWNLOADS, sub)
        if not os.path.isdir(src_dir):
            print(f"[skip] {src_dir} 不存在")
            continue
        os.makedirs(cfg["dir"], exist_ok=True)
        manifest = load_manifest(os.path.join(cfg["dir"], "manifest.json"))
        seen = set(e.get("sha256") for e in manifest["entries"])
        num = max_number(cfg["dir"], cfg["prefix"]) + 1
        ok = dup = fail = 0
        for name in sorted(os.listdir(src_dir)):
            if not name.lower().endswith((".wav", ".mp3")):
                continue
            try:
                seg = AudioSegment.from_file(os.path.join(src_dir, name))
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
                out_name = f"{cfg['prefix']} ({num}).wav"
                if not args.dry_run:
                    seg.export(os.path.join(cfg["dir"], out_name), format="wav")
                manifest["entries"].append({
                    "file": out_name,
                    "source_pack": sub,
                    "original": name,
                    "original_rel": f"{sub}/{name}",
                    "license": LICENSE,
                    "duration_s": round(seg.duration_seconds, 2),
                    "sha256": h,
                })
                num += 1
                ok += 1
            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"[fail] {name}: {e}", file=sys.stderr)
        manifest["generated"] = datetime.now().isoformat(timespec="seconds")
        print(f"[{cfg['prefix']}] 入库 {ok}（去重 {dup}、失败 {fail}）→ {cfg['dir']} "
              f"manifest 共 {len(manifest['entries'])} 条")
        if not args.dry_run:
            with open(os.path.join(cfg["dir"], "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
