#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""乐器池内容查重扫描 v2（只读：不移动、不删除、不修改任何素材）。

原则：**重名 ≠ 重复，元数据 ≠ 内容**。判定重复唯一依据是文件内容：
  1) 对每个文件计算「大小 + 头 8KB + 尾 8KB」SHA-256 作为候选签名（不信任任何
     manifest 字段；manifest 里的 sha256 仅用于交叉核对报告，不参与判重）；
  2) 候选签名相同的组（>=2 成员）**逐文件全量 SHA-256 复核**后重新分组；
  3) 只有「大小 + 全量 SHA-256」完全一致才记为重复；
  4) 复核过程中顺带核对 manifest sha256 与文件实际内容是否一致（stale hash 报告）。

用法：
  python dedupe_scan.py --root <MUSICKIT_ROOT> --out <MUSICKIT_ROOT>\dedupe_report_20260818.json
"""
import argparse
import hashlib
import json
import os
from collections import defaultdict

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]

AUDIO_EXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")
HEAD_TAIL = 8192


def quick_sig(path: str, size: int) -> str:
    """候选签名 = 大小 + 头 8KB + 尾 8KB（小文件全读）。"""
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(HEAD_TAIL))
        if size > HEAD_TAIL * 2:
            f.seek(-HEAD_TAIL, os.SEEK_END)
            h.update(f.read(HEAD_TAIL))
        else:
            f.seek(0)
            h.update(f.read())
    return h.hexdigest()


def full_sha(path: str) -> str:
    """文件内容的完整 SHA-256（不含大小前缀）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(root: str, pool: str) -> list:
    pool_dir = os.path.join(root, pool)
    if not os.path.isdir(pool_dir):
        return []
    manifest = {}
    mp = os.path.join(pool_dir, "manifest.json")
    if os.path.isfile(mp):
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            for e in data.get("entries", []):
                if isinstance(e, dict) and e.get("file") and e.get("sha256"):
                    manifest[e["file"]] = e["sha256"]
        except Exception:
            pass
    out = []
    for r, _dirs, names in os.walk(pool_dir):
        for n in sorted(names):
            if not n.lower().endswith(AUDIO_EXT):
                continue
            path = os.path.join(r, n)
            rel = os.path.relpath(path, root).replace("\\", "/")
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            out.append({"pool": pool, "path": path, "rel": rel,
                        "size": size, "manifest_sha": manifest.get(n)})
    return out


def main():
    p = argparse.ArgumentParser(description="乐器池内容查重 v2（纯内容判定，只读）")
    p.add_argument("--root", default=r"<MUSICKIT_ROOT>")
    p.add_argument("--pools", default=None, help="逗号分隔池名（默认全部 13 池）")
    p.add_argument("--out", default=None, help="重复组明细 JSON 输出路径")
    args = p.parse_args()
    pools = [x.strip() for x in args.pools.split(",")] if args.pools else POOLS

    entries = []
    for pool in pools:
        pool_entries = collect(args.root, pool)
        print(f"[scan] {pool}: {len(pool_entries)} 个音频文件")
        entries.extend(pool_entries)
    print(f"[scan] 合计 {len(entries)} 个文件")

    # 阶段 1：候选签名（不信任任何 manifest 字段）
    quick_groups = defaultdict(list)
    for e in entries:
        quick_groups[(e["size"], quick_sig(e["path"], e["size"]))].append(e)

    # 阶段 2：候选组（>=2）逐文件全量复核；单成员组直接视为唯一
    full_groups = defaultdict(list)
    stale = []
    checked = 0
    for (size, _q), group in quick_groups.items():
        if len(group) < 2:
            # 单成员 = 唯一内容，直接跳过（绝不用共享哨兵键，避免同尺寸不同内容误撞组）
            continue
        for e in group:
            sha = full_sha(e["path"])
            checked += 1
            if e["manifest_sha"] and e["manifest_sha"] != sha:
                stale.append({"pool": e["pool"], "rel": e["rel"],
                              "manifest_sha256": e["manifest_sha"],
                              "actual_sha256": sha})
            full_groups[(size, sha)].append(e)
    print(f"[scan] 候选组全量复核 {checked} 个文件")

    dup_groups = {k: v for k, v in full_groups.items() if len(v) >= 2}

    per_pool = defaultdict(lambda: [0, 0])
    cross = 0
    for (_size, _sha), group in dup_groups.items():
        if len({e["pool"] for e in group}) > 1:
            cross += 1
        for e in group:
            per_pool[e["pool"]][0] += 1
            per_pool[e["pool"]][1] += e["size"]

    print("\n每池重复统计（重复文件数 / 全组仅留 1 份可回收的冗余字节）：")
    for pool in pools:
        n, wasted = per_pool[pool]
        print(f"  {pool:<10} {n:>6} 个重复文件  {wasted / 1e6:>10.1f} MB 冗余")
    total_n = sum(v[0] for v in per_pool.values())
    total_wasted = sum(v[1] for v in per_pool.values())
    print(f"  {'合计':<10} {total_n:>6} 个重复文件  {total_wasted / 1e9:>10.2f} GB 冗余")
    print(f"  重复组数：{len(dup_groups)}（其中跨池 {cross} 组）")
    print(f"  manifest sha256 与实际内容不一致（stale）：{len(stale)} 个文件")

    if args.out:
        out = {
            "method": "纯内容判定：大小+首尾8KB候选签名 -> 候选组全量SHA-256复核；"
                      "manifest sha256 仅交叉核对，不参与判重（重名!=重复）",
            "root": args.root,
            "pools": pools,
            "total_files": len(entries),
            "full_hashed_files": checked,
            "duplicate_groups": len(dup_groups),
            "cross_pool_groups": cross,
            "duplicate_files": total_n,
            "wasted_bytes": total_wasted,
            "stale_manifest_hashes": stale,
            "groups": [
                {"size": size, "sha256": sha,
                 "members": [{"pool": e["pool"], "rel": e["rel"], "size": e["size"]}
                             for e in sorted(group, key=lambda x: (x["pool"], x["rel"]))]}
                for (size, sha), group in sorted(dup_groups.items(),
                                                 key=lambda kv: -len(kv[1]))
            ],
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n明细已写入：{args.out}")


if __name__ == "__main__":
    main()