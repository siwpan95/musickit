#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""给 13 池 manifest 条目标注 content_kind（素材形态），供桥接器旋律层选音优先 loop。

分类规则（按顺序首中即停）：
  stem        — 整曲 stem 命名（bass (N).wav 等）或文件名含 "stem" 或时长 > 60s
  loop        — 文件名/原始路径含 loop 或 BPM 提示；或已知时长 2~60s 且无其它特征
  single_note — 文件名含单音标记（如 C2 / D3 / F#4，"EHn_susDyn_..._D3"）
  one_shot    — 已知时长 < 2s
  unknown     — 无任何特征（保持现状）

用法：
  python tag_content_kind.py --root G:\musickit            # dry-run
  python tag_content_kind.py --root G:\musickit --apply    # 备份后原地改写 manifest
"""
import argparse
import json
import os
import re
import shutil
from collections import Counter

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]

STEM_RE = re.compile(r"^(bass|drum|guita) \(\d{1,3}\)\.(wav|mp3|flac|aiff|aif)$", re.I)
LOOP_RE = re.compile(r"loop|_lp\b", re.I)
BPM_RE = re.compile(r"\d{2,3}\s*bpm", re.I)
NOTE_RE = re.compile(r"(^|[^a-z0-9])([a-g](?:#|b)?\d)([^a-z0-9]|$)", re.I)


def classify(e: dict) -> str:
    fname = e.get("file") or ""
    rel = " ".join([e.get("original_rel") or "", e.get("original") or ""])
    dur = e.get("duration_s")
    if STEM_RE.match(fname) or "stem" in fname.lower():
        return "stem"
    if LOOP_RE.search(fname) or BPM_RE.search(fname + " " + rel):
        return "loop"
    if NOTE_RE.search(fname):
        return "single_note"
    if isinstance(dur, (int, float)):
        if dur < 2:
            return "one_shot"
        if dur > 60:
            return "stem"
        return "loop"
    return "unknown"


def process_pool(root: str, pool: str, apply: bool) -> Counter:
    mp = os.path.join(root, pool, "manifest.json")
    if not os.path.isfile(mp):
        return Counter()
    with open(mp, "r", encoding="utf-8") as f:
        data = json.load(f)
    dist = Counter()
    for e in data.get("entries", []):
        if not isinstance(e, dict):
            continue
        kind = classify(e)
        dist[kind] += 1
        if apply:
            e["content_kind"] = kind
    if apply:
        backup_dir = os.path.join(root, "archived", "manifest_backup_content_kind_20260818")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(mp, os.path.join(backup_dir, f"{pool}_manifest.json"))
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return dist


def main():
    p = argparse.ArgumentParser(description="content_kind 素材形态标注")
    p.add_argument("--root", default=r"G:\musickit", help="musickit 根目录")
    p.add_argument("--apply", action="store_true", help="备份后原地改写 manifest")
    args = p.parse_args()

    total = Counter()
    print(f"{'pool':<10} {'stem':>6} {'loop':>6} {'single_note':>11} {'one_shot':>9} {'unknown':>8}")
    for pool in POOLS:
        dist = process_pool(args.root, pool, args.apply)
        total.update(dist)
        print(f"{pool:<10} {dist['stem']:>6} {dist['loop']:>6} "
              f"{dist['single_note']:>11} {dist['one_shot']:>9} {dist['unknown']:>8}")
    print("-" * 56)
    print(f"{'TOTAL':<10} {total['stem']:>6} {total['loop']:>6} "
          f"{total['single_note']:>11} {total['one_shot']:>9} {total['unknown']:>8}")
    print("\n模式：" + ("已写入（备份 archived/manifest_backup_content_kind_20260818/）"
                       if args.apply else "dry-run（加 --apply 落盘）"))


if __name__ == "__main__":
    main()
