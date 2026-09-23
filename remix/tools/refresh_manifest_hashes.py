#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""重算 manifest sha256 戳（只读源文件，--apply 时备份后改写 manifest）。

背景：2026-08-18 校验发现 84%（1,563/1,869）的 manifest sha256 与实际内容不符
（入库脚本当年盖错戳）。原则：元数据必须来自内容——本工具按 (subcategory, 文件名)
定位文件、全量哈希后重写 sha256 字段。

用法：
  python refresh_manifest_hashes.py --root <MUSICKIT_ROOT>            # dry-run（仅统计）
  python refresh_manifest_hashes.py --root <MUSICKIT_ROOT> --apply    # 备份并重写
  python refresh_manifest_hashes.py --root <MUSICKIT_ROOT> --all --apply  # 全库补写（约 33k 文件，耗时）
"""
import argparse
import hashlib
import json
import os
import shutil
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
    p = argparse.ArgumentParser(description="重算 manifest sha256 戳")
    p.add_argument("--root", default=r"<MUSICKIT_ROOT>")
    p.add_argument("--apply", action="store_true", help="备份后原地改写 manifest")
    p.add_argument("--all", action="store_true",
                   help="为全部条目录入 sha256（默认仅修正已有记录者）")
    args = p.parse_args()

    total = 0
    updated = 0
    missing_files = 0
    per_pool = defaultdict(int)
    for pool in POOLS:
        mp = os.path.join(args.root, pool, "manifest.json")
        if not os.path.isfile(mp):
            continue
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("entries", []):
            if not isinstance(e, dict):
                continue
            if not args.all and not e.get("sha256"):
                continue
            total += 1
            sub = e.get("subcategory") or "(root)"
            if sub == "(root)":
                path = os.path.join(args.root, pool, e["file"])
            else:
                path = os.path.join(args.root, pool, sub, e["file"])
            if not os.path.isfile(path):
                missing_files += 1
                continue
            actual = full_sha(path)
            if e.get("sha256") != actual:
                updated += 1
                per_pool[pool] += 1
                if args.apply:
                    e["sha256"] = actual
        if args.apply:
            backup_dir = os.path.join(args.root, "archived",
                                      "manifest_backup_hashes_20260818")
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(mp, os.path.join(backup_dir, f"{pool}_manifest.json"))
            with open(mp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"处理条目 {total}；需修正 sha256：{updated}；文件缺失：{missing_files}")
    for pool in POOLS:
        if per_pool[pool]:
            print(f"  {pool:<10} {per_pool[pool]} 条")
    print("模式：" + ("已写入（备份 archived/manifest_backup_hashes_20260818/）"
                     if args.apply else "dry-run（加 --apply 落盘）"))


if __name__ == "__main__":
    main()
