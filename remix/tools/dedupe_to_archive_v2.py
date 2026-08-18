#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""按 dedupe_report（纯内容判定）把冗余副本移入 archived（只移不删，全程可回溯）。\n\n原则：重名 ≠ 重复——移动计划只来自内容级查重报告；manifest 条目按\n(subcategory, 文件名) 精确移除，同名不同内容的条目绝不被误删。

规则（与项目 archived 政策一致）：
  - 每个重复组在每个池内保留 1 份（按 rel 路径排序的最小者，即编号最小/字典序最前），
    其余副本移动到 archived/dedupe_pools_<日期>/<rel>；
  - 移动后同步更新各池 manifest.json（移除已移动条目）；
  - 移动记录写 archived/dedupe_pools_<日期>/move_manifest.json；
  - 默认 dry-run（只打印计划），加 --apply 才执行。

用法：
  python dedupe_to_archive_v2.py --report G:\musickit\dedupe_report_20260817.json \
      --root G:\musickit                 # dry-run
  python dedupe_to_archive_v2.py ... --apply
"""
import argparse
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]


def entry_identity(rel: str) -> tuple[str, str]:
    """报告相对路径 -> (subcategory, 文件名)。重名不同子目录 = 不同身份。"""
    parts = rel.split("/")
    sub = "/".join(parts[1:-1]) if len(parts) > 2 else "(root)"
    return sub, parts[-1]


def plan(report: dict) -> list[dict]:
    """返回 [(pool, src_rel, group_size), ...] 计划移动清单（不含每组保留件）。"""
    moves = []
    for g in report.get("groups", []):
        per_pool: dict[str, list[str]] = defaultdict(list)
        for m in g["members"]:
            per_pool[m["pool"]].append(m["rel"])
        for pool, rels in per_pool.items():
            if len(rels) <= 1:
                continue
            for rel in sorted(rels)[1:]:          # 保留字典序最小（编号最小）
                moves.append((pool, rel, len(rels)))
    return moves


def main():
    p = argparse.ArgumentParser(description="按查重报告移动冗余副本进 archived")
    p.add_argument("--report", required=True, help="dedupe_scan.py 产出的报告 JSON")
    p.add_argument("--root", default=r"G:\musickit")
    p.add_argument("--apply", action="store_true", help="执行移动（默认 dry-run）")
    args = p.parse_args()

    with open(args.report, encoding="utf-8") as f:
        report = json.load(f)
    moves = plan(report)
    by_pool = defaultdict(int)
    total_bytes = 0
    for pool, rel, _n in moves:
        by_pool[pool] += 1
        src = os.path.join(args.root, rel.replace("/", os.sep))
        try:
            total_bytes += os.path.getsize(src)
        except OSError:
            pass

    print(f"计划移动 {len(moves)} 个冗余副本，可回收约 {total_bytes / 1e9:.2f} GB：")
    for pool in POOLS:
        if by_pool[pool]:
            print(f"  {pool:<10} {by_pool[pool]:>6} 个")

    if not args.apply:
        print("\n模式：dry-run（加 --apply 执行；目标 archived/dedupe_pools_*/）")
        return

    stamp = datetime.now().strftime("%Y%m%d")
    base = os.path.join(args.root, "archived", f"dedupe_pools_{stamp}")
    os.makedirs(base, exist_ok=True)
    records = []
    moved_by_pool = defaultdict(set)

    for pool, rel, _n in moves:
        src = os.path.join(args.root, rel.replace("/", os.sep))
        dst = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            records.append({"pool": pool, "rel": rel, "error": "源文件不存在"})
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            records.append({"pool": pool, "rel": rel, "error": "目标已存在"})
            continue
        shutil.move(src, dst)
        # 条目身份 = (subcategory, 文件名)：重名不等于同一文件，绝不按裸文件名删条目
        parts = rel.split("/")
        sub = "/".join(parts[1:-1]) if len(parts) > 2 else "(root)"
        moved_by_pool[pool].add((sub, parts[-1]))
        records.append({"pool": pool, "rel": rel, "moved_to": dst})

    # 同步各池 manifest（按 (subcategory, 文件名) 精确移除已移动条目；
    # 同名但不同子目录/不同内容的条目绝不被误删）
    for pool, keys in moved_by_pool.items():
        mp = os.path.join(args.root, pool, "manifest.json")
        if not os.path.isfile(mp):
            continue
        with open(mp, encoding="utf-8") as f:
            data = json.load(f)
        before = len(data.get("entries", []))
        data["entries"] = [e for e in data.get("entries", [])
                           if not isinstance(e, dict)
                           or ((e.get("subcategory") or "(root)"), e.get("file")) not in keys]
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [manifest] {pool}: {before} -> {len(data['entries'])} 条")

    rec_path = os.path.join(base, "move_manifest.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    errs = [r for r in records if "error" in r]
    print(f"\n已移动 {len(records) - len(errs)} 个文件；记录：{rec_path}")
    for r in errs:
        print(f"  ⚠ {r['pool']}/{r['rel']}: {r['error']}")
    print("提示：移动后请重跑 build_manifest_index.py 刷新总索引。")


if __name__ == "__main__":
    main()
