#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""扫描各素材池 manifest 的 license / license_tier 分布（数据治理巡检）。

输出：stdout 汇总表 +（可选）license_audit.json 全量明细。
用法：python audit_licenses.py --root <MUSICKIT_ROOT> [--out license_audit.json]
"""
import argparse
import json
import os
from collections import Counter

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]


def main():
    p = argparse.ArgumentParser(description="授权治理巡检")
    p.add_argument("--root", default=r"<MUSICKIT_ROOT>", help="musickit 根目录")
    p.add_argument("--out", default=None, help="明细输出路径（可选）")
    args = p.parse_args()

    detail: dict[str, dict] = {}
    grand_tier = Counter()
    grand_license = Counter()
    print(f"{'pool':<10} {'entries':>8}   license_tier 分布")
    for pool in POOLS:
        mp = os.path.join(args.root, pool, "manifest.json")
        if not os.path.isfile(mp):
            print(f"{pool:<10} {'(无 manifest)':>8}")
            continue
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = [e for e in data.get("entries", []) if isinstance(e, dict)]
        tier = Counter(e.get("license_tier") or "(未标注)" for e in entries)
        lic = Counter(e.get("license") or "(空)" for e in entries)
        grand_tier.update(tier)
        grand_license.update(lic)
        detail[pool] = {"entries": len(entries), "tier": dict(tier),
                        "license": dict(lic)}
        print(f"{pool:<10} {len(entries):>8}   {dict(tier)}")

    print("\n总计 license_tier 分布：", dict(grand_tier))
    empty_lic = grand_license.get("(空)", 0)
    print(f"license 为空条目：{empty_lic}；不同 license 文案数：{len(grand_license)}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"pools": detail,
                       "total_tier": dict(grand_tier)}, f,
                      ensure_ascii=False, indent=2)
        print(f"明细已写入：{args.out}")


if __name__ == "__main__":
    main()
