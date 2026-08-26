# -*- coding: utf-8 -*-
"""pool_plugin.py —— 采样池插件协议（musickit S5 · 2026-08-25）

把 13 个采样池升级为正式插件协议（零迁移：license_tier 已在各池 manifest.json 的逐文件记录里）：
- 插件 = 一个采样池目录（id=目录名；manifest.json = 逐文件授权记录）；
- 注册即回滚：register/unregister 全量可逆；
- 校验 fail-loud：池目录存在 + manifest.json 存在；
- license_tier 聚合：流式扫描 manifest.json 统计 free/pack/restricted/unknown（不整载入内存）；
- 日志即事实源：pool_scan 事件写 JSONL（与 WorldLog 同构）。

审计 CLI：python pool_plugin.py --dump [--json] / --check
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

POOLS = ["acapella", "animal", "bass", "brass", "cowbell", "drum",
         "ethnic", "guita", "keys", "sfx", "strings", "synth", "woodwind"]
REGISTRY_VERSION = "1.0.0"
MUSICKIT_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG = MUSICKIT_ROOT / "data" / "pool_events.log"
TIER_RE = re.compile(r'"license_tier"\s*:\s*"([a-z]+)"')

__all__ = ["PoolRegistry", "POOLS", "REGISTRY_VERSION"]


def count_tiers(manifest_path: Path) -> dict:
    """流式扫描逐文件 manifest，统计各 license_tier 数量。"""
    stats = {"free": 0, "pack": 0, "restricted": 0, "unknown": 0, "total": 0}
    try:
        with open(manifest_path, encoding="utf-8", errors="replace") as fp:
            for line in fp:
                for m in TIER_RE.finditer(line):
                    tier = m.group(1)
                    if tier in stats:
                        stats[tier] += 1
                        stats["total"] += 1
    except OSError:
        pass
    return stats


def validate_pool(pool_id: str, root: Path) -> list:
    """校验单个采样池插件，返回问题列表（空 = 通过）。"""
    errs = []
    d = root / pool_id
    if not d.is_dir():
        errs.append(f"池目录不存在: {d}")
    if not (d / "manifest.json").is_file():
        errs.append(f"manifest.json 缺失: {d / 'manifest.json'}")
    return errs


class PoolRegistry:
    """采样池插件注册表：装配/回滚/审计（数据源 = 各池 manifest.json）。"""

    def __init__(self, root: Path | str = MUSICKIT_ROOT, log_path: Path | str | None = None):
        self._root = Path(root)
        self._pools: dict = {}
        self._log_path = Path(log_path) if log_path is not None else None
        self._seq = 0

    # ---- 装配（注册即回滚） ----
    def register(self, pool_id: str, version: str = "1.0.0") -> str:
        errs = validate_pool(pool_id, self._root)
        if errs:
            raise ValueError(f"采样池 '{pool_id}' 校验失败: {'; '.join(errs)}")
        stats = count_tiers(self._root / pool_id / "manifest.json")
        self._pools[pool_id] = {
            "id": pool_id, "dir": str(self._root / pool_id),
            "version": version, "stats": stats,
            "release_safe": stats["free"] + stats["pack"],
        }
        return pool_id

    def register_all(self, pools: list = POOLS) -> int:
        for p in pools:
            self.register(p)
        return len(self._pools)

    def unregister(self, pool_id: str) -> dict | None:
        return self._pools.pop(pool_id, None)

    # ---- 审计 ----
    def dump(self) -> list:
        out = []
        for pid in sorted(self._pools):
            p = self._pools[pid]
            s = p["stats"]
            out.append({
                "id": pid, "version": p["version"],
                "free": s["free"], "pack": s["pack"],
                "restricted": s["restricted"], "unknown": s["unknown"],
                "total": s["total"], "release_safe": p["release_safe"],
            })
        return out

    @property
    def pool_ids(self) -> list:
        return sorted(self._pools)

    def __len__(self) -> int:
        return len(self._pools)

    # ---- 事件日志 ----
    def set_log(self, path: Path | str):
        self._log_path = Path(path)

    def log_scan(self, **payload):
        if self._log_path is None:
            return
        self._seq += 1
        entry = {"seq": self._seq,
                 "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "type": "pool_scan"}
        entry.update(payload)
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def _main(argv) -> int:
    p = argparse.ArgumentParser(prog="python pool_plugin.py", description="采样池插件注册表审计")
    p.add_argument("--dump", action="store_true", help="打印采样池插件清单")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--check", action="store_true", help="校验全部采样池（exit 0=全通过）")
    args = p.parse_args(argv)

    reg = PoolRegistry()
    problems = []
    for pid in POOLS:
        try:
            reg.register(pid)
        except ValueError as e:
            problems.append(str(e))

    if args.json:
        print(json.dumps({"version": REGISTRY_VERSION, "count": len(reg),
                          "pools": reg.dump(), "problems": problems},
                         ensure_ascii=False, indent=2))
        return 1 if problems else 0
    if args.check or args.dump:
        total_safe = 0
        for d in reg.dump():
            total_safe += d["release_safe"]
            print(f"  {d['id']:12} v{d['version']}  free={d['free']} pack={d['pack']} "
                  f"restricted={d['restricted']} unknown={d['unknown']} (total={d['total']})")
        print(f"[{'check' if args.check else 'dump'}] {'通过' if not problems else '失败'}："
              f"{len(reg)} 采样池，release-safe 可用 {total_safe} 文件" +
              (f"，问题：{problems}" if problems else ""))
        return 1 if problems else 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
