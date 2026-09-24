"""Phase 5：把 <CSMUSIC_STEMS_ROOT>（默认 <工作区>\\assets\\csmusic_stems）（CS 游戏音乐 Demucs 分离库，持续增⻓）增量并入 musickit 物料。

对每首「完成」的歌曲（bass/drums/other/vocals 四轨齐全 且 无 htdemucs 临时目录）：
  - bass.wav   → <MUSICKIT_ROOT>\\bass\\bass (N).wav
  - drums.wav  → <MUSICKIT_ROOT>\\drum\\drum (N).wav
  - other.wav  → <MUSICKIT_ROOT>\\guita\\guita (N).wav      # guita = other 轨当吉他，项目约定
  （vocals.wav 不并入：musickit/animal 为动物叫声 one-shot，非歌曲人声）
  - 三轨共享同一编号 N（与 radio stem 约定一致，便于 stems_song_map 关联同一首歌）
  - 各目录 manifest.json 追加条目（source_pack="csmusic"，original=歌曲目录名）
  - 原样拷贝（不做归一化/时长截断），与 radio 整曲 stem 同性质

「进行中」歌曲（含 htdemucs 临时目录 或 stem 不足 4 个）跳过，等后续自动化轮次并入。
幂等：以 manifest 中已存在的 csmusic 条目（original==歌曲目录名）为准，跳过已并入歌曲。
用法: python ingest_csmusic.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import wave
from datetime import datetime
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

ROOT = str(_MK_ROOT)
# 2026-09-23 去本地化：原路径已失效，stem 库现为 <工作区>\assets\csmusic_stems
CS = str(Path(os.environ.get("CSMUSIC_STEMS_ROOT") or (_MK_ROOT.parent.parent / "assets" / "csmusic_stems")))
PROGRESS = os.path.join(ROOT, "remix", "tools", "csmusic_ingest_progress.json")
CATS = {
    "bass": str(_MK_ROOT / "bass"),
    "drum": str(_MK_ROOT / "drum"),
    "guita": str(_MK_ROOT / "guita"),
}
CS_STEM = {"bass": "bass.wav", "drum": "drums.wav", "guita": "other.wav"}
# 与 subdivide_manifests.py 对 csmusic 物料的子类落位保持一致
CS_SUBFOLDER = {"bass": "bass_misc", "drum": "drums_acoustic", "guita": "guitar_electric"}
LICENSE = "Demucs 分离自 CS 游戏音乐（粉丝提取，商用前需确认授权）"
CS_STEM_FILES = ["bass.wav", "drums.wav", "other.wav", "vocals.wav"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_s(path):
    try:
        with wave.open(path, "rb") as w:
            fr = w.getframerate()
            nf = w.getnframes()
            return round(nf / fr, 2) if fr else None
    except Exception:
        return None


def max_num(cat_dir, prefix):
    # 递归扫描：细分后编号文件已落到子类子目录，必须 walk 而非仅看根
    best = 0
    if not os.path.isdir(cat_dir):
        return best
    for _root, _dirs, _names in os.walk(cat_dir):
        for name in _names:
            m = re.search(re.escape(prefix) + r" \((\d+)\)\.wav", name)
            if m:
                best = max(best, int(m.group(1)))
    return best


def is_complete(song):
    dp = os.path.join(CS, song)
    if not os.path.isdir(dp):
        return False
    if any(os.path.isdir(os.path.join(dp, x)) for x in os.listdir(dp)):
        return False  # htdemucs 临时目录 => 分离进行中
    present = sum(
        1 for f in CS_STEM_FILES if os.path.isfile(os.path.join(dp, f))
    )
    return present == 4


def load_manifest(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def save_manifest(path, m):
    m["generated"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifests = {c: load_manifest(os.path.join(CATS[c], "manifest.json")) for c in CATS}

    # 已并入的 csmusic 歌曲（以 manifest 为准，保证幂等）
    already = set()
    for c in CATS:
        for e in manifests[c]["entries"]:
            if e.get("source_pack") == "csmusic" and e.get("original"):
                already.add(e["original"])

    # 起始编号：三类现有最大编号 +1（共享 N）
    start = max(max_num(CATS[c], c) for c in CATS) + 1

    prog = {}
    if os.path.exists(PROGRESS):
        with open(PROGRESS, "r", encoding="utf-8") as f:
            prog = json.load(f)
    merged_log = prog.get("merged", {})

    n = start
    ok = skip = 0
    for song in sorted(os.listdir(CS)):
        dp = os.path.join(CS, song)
        if not os.path.isdir(dp):
            continue
        if song in already:
            skip += 1
            continue
        if not is_complete(song):
            continue  # 进行中，留待后续轮次
        nums = {c: n for c in CATS}
        for c, stem in CS_STEM.items():
            src = os.path.join(dp, stem)
            sub = CS_SUBFOLDER[c]
            dst = os.path.join(CATS[c], sub, f"{c} ({nums[c]}).wav")
            if not args.dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            dur = duration_s(src)
            h = sha256_file(src)
            manifests[c]["entries"].append({
                "file": f"{c} ({nums[c]}).wav",
                "subcategory": sub,
                "source_pack": "csmusic",
                "original": song,
                "original_rel": f"csmusic_stems/{song}",
                "license": LICENSE,
                "duration_s": dur,
                "sha256": h,
            })
        merged_log[song] = {"nums": nums, "status": "merged"}
        n += 1
        ok += 1

    if not args.dry_run:
        for c in CATS:
            save_manifest(os.path.join(CATS[c], "manifest.json"), manifests[c])
        prog["merged"] = merged_log
        prog["generated"] = datetime.now().isoformat(timespec="seconds")
        with open(PROGRESS, "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False, indent=1)

    print(f"本次并入 {ok} 首；跳过已并入 {skip}；编号起点 {start} → 下一起点 {n}")


if __name__ == "__main__":
    main()
