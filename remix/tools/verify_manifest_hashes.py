#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""manifest sha256 戳专项校验（只读）。

只对「manifest 里记录了 sha256」的文件做全量哈希比对（约 3~4k 个文件，不扫全库），
报告有多少记录与实际内容不符（stale）。原则：元数据 ≠ 内容——查重绝不使用这些戳，
本工具只是把戳错误量化出来供数据治理。

用法：python verify_manifest_hashes.py --root G:\musickit [--out stale_manifest_hashes.json]
"""
import argparse
import hashlib
import json
import os
from collections import defaultdict

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]


def full_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description="manifest sha256 戳校验（只读）")
    p.add_argument("--root", default=r"G:\musickit")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    checked = 0
    stale = []
    per_pool = defaultdict(int)
    for pool in POOLS:
        mp = os.path.join(args.root, pool, "manifest.json")
        if not os.path.isfile(mp):
            continue
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("entries", []):
            if not isinstance(e, dict) or not e.get("sha256"):
                continue
            # 依据 subcategory 定位真实文件（同名不同子目录 = 不同文件）
            sub = e.get("subcategory") or "(root)"
            if sub == "(root)":
                path = os.path.join(args.root, pool, e["file"])
            else:
                path = os.path.join(args.root, pool, sub, e["file"])
            if not os.path.isfile(path):
                stale.append({"pool": pool, "file": e["file"],
                              "subcategory": sub, "issue": "文件不存在"})
                per_pool[pool] += 1
                continue
            actual = full_sha(path)
            checked += 1
            if actual != e["sha256"]:
                stale.append({"pool": pool, "file": e["file"],
                              "subcategory": sub,
                              "manifest_sha256": e["sha256"],
                              "actual_sha256": actual})
                per_pool[pool] += 1

    print(f"校验了 {checked} 个带 manifest sha256 的文件")
    print(f"记录与实际内容不一致：{len(stale)} 个")
    for pool in POOLS:
        if per_pool[pool]:
            print(f"  {pool:<10} {per_pool[pool]} 个")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"checked": checked, "stale_count": len(stale),
                       "stale": stale}, f, ensure_ascii=False, indent=2)
        print(f"明细已写入：{args.out}")


if __name__ == "__main__":
    main()
