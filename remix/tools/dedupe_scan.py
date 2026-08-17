#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""乐器池内容查重扫描（只读：不移动、不删除、不修改任何素材）。

口径（与项目评估报告一致，并做全量复核）：
  1) manifest 已记录 sha256 的条目：直接用 (size, sha256) 分组（零读取）；
  2) 其余文件：按「文件大小 + 头 8KB + 尾 8KB」的 SHA-256 粗分组；
  3) 粗分组内成员 >=2 时，组内做全文件 SHA-256 复核（防止签名误报）；
  4) 最终按 (size, sha256_full) 分组，成员 >=2 即为重复。

产出：
  - stdout：每池重复数 / 冗余字节 / 跨池重复组汇总
  - --out JSON：重复组明细（组号 -> [{"pool", "rel_path", "size"}]）

用法：
  python dedupe_scan.py --root G:\musickit --out G:\musickit\dedupe_report_20260817.json
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


def full_sig(path: str, size: int) -> str:
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(root: str, pool: str) -> list[dict]:
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
                        "size": size, "sha": manifest.get(n)})
    return out


def main():
    p = argparse.ArgumentParser(description="乐器池内容查重（只读）")
    p.add_argument("--root", default=r"G:\musickit")
    p.add_argument("--pools", default=None, help="逗号分隔池名（默认全部 13 池）")
    p.add_argument("--out", default=None, help="重复组明细 JSON 输出路径")
    args = p.parse_args()
    pools = [x.strip() for x in args.pools.split(",")] if args.pools else POOLS

    entries = []
    for pool in pools:
        pool_entries = collect(args.root, pool)
        print(f"[scan] {pool}: {len(pool_entries)} 个音频文件")
        entries.extend(pool_entries)
    print(f"[scan] 合计 {len(entries)} 个文件，开始分组…")

    full_groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    quick_groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for e in entries:
        if e["sha"]:
            full_groups[(e["size"], e["sha"])].append(e)
        else:
            quick_groups[(e["size"], quick_sig(e["path"], e["size"]))].append(e)

    # 粗分组复核：组内全量哈希
    checked = 0
    for (size, _q), group in list(quick_groups.items()):
        if len(group) >= 2:
            for e in group:
                full_groups[(size, full_sig(e["path"], size))].append(e)
                checked += 1
        else:
            full_groups[(size, "quick-unique")].append(group[0])
    print(f"[scan] 全量哈希复核 {checked} 个文件")

    dup_groups = {k: v for k, v in full_groups.items() if len(v) >= 2}

    per_pool = defaultdict(lambda: [0, 0])   # pool -> [重复文件数, 冗余字节]
    cross = 0
    for (_size, _sha), group in dup_groups.items():
        pools_in = {e["pool"] for e in group}
        if len(pools_in) > 1:
            cross += 1
        for e in group:
            per_pool[e["pool"]][0] += 1
            per_pool[e["pool"]][1] += e["size"]

    print("\n每池重复统计（重复文件数 / 冗余字节 = 每个重复组只保留 1 份可回收的空间）：")
    for pool in pools:
        n, wasted = per_pool[pool]
        print(f"  {pool:<10} {n:>6} 个重复文件  {wasted / 1e6:>10.1f} MB 冗余")
    total_n = sum(v[0] for v in per_pool.values())
    total_wasted = sum(v[1] for v in per_pool.values())
    print(f"  {'合计':<10} {total_n:>6} 个重复文件  {total_wasted / 1e9:>10.2f} GB 冗余")
    print(f"  重复组数：{len(dup_groups)}（其中跨池 {cross} 组）")

    if args.out:
        out = {
            "root": args.root,
            "pools": pools,
            "total_files": len(entries),
            "duplicate_groups": len(dup_groups),
            "cross_pool_groups": cross,
            "duplicate_files": total_n,
            "wasted_bytes": total_wasted,
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
