"""element_pool — 把提示词的 `elements[]`（氛围词）映射成真实素材（架构文档 §7.3 第 2 项）。

背景：`elements` 里是「雨声 / 霓虹 / 街道 / 森林」这类氛围词，此前被完全丢弃 ——
引擎对这些词没有任何响应，写不写它们出来的曲子一模一样。

做法：词表 + 素材子串匹配（`music/element_pools.json`，改词表不动代码）。
- 命中 → 从对应池挑 1 条真实素材，作为点缀层（sfx/animal 在引擎里天然走 ROLE_ACCENT）
- 未命中 → 记入 gaps，**绝不假映射**（与 instruments 的处理口径一致）
"""
from __future__ import annotations

import json
import os
import random
from functools import lru_cache

_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "element_pools.json")


@lru_cache(maxsize=1)
def _load_rules() -> list[dict]:
    try:
        with open(_TABLE, encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data.get("rules") or []
                if r.get("match") and r.get("pool")]
    except Exception:  # noqa: BLE001
        return []


def _match_rule(element: str) -> dict | None:
    text = str(element).strip().lower()
    if not text:
        return None
    for rule in _load_rules():
        for kw in rule["match"]:
            if str(kw).lower() in text:
                return rule
    return None


def resolve(
    elements: list[str] | None,
    entries_by_pool: dict[str, dict],
    root: str,
    rng: random.Random | None = None,
    max_accents: int = 2,
    skip: set[str] | None = None,
) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """把氛围词解析成 (pool, path, element, why) 列表 + 未命中词列表。

    - 最多 `max_accents` 层（点缀层多了会吵）
    - 同一文件不重复选（skip 里是已用过的路径）
    - 池内无匹配素材时该元素记入 gaps
    """
    rng = rng or random.Random(0)
    used = set(skip or ())
    picks: list[tuple[str, str, str, str]] = []
    gaps: list[str] = []

    for el in (elements or []):
        if len(picks) >= max_accents:
            break
        rule = _match_rule(el)
        if not rule:
            gaps.append(f"{el} [无匹配规则]")
            continue
        pool = rule["pool"]
        pool_entries = entries_by_pool.get(pool) or {}
        keywords = [str(k).lower() for k in rule.get("file_match") or []]
        cands = []
        for fname, entry in pool_entries.items():
            if not keywords:
                cands.append(fname)
                continue
            hay = " ".join(str(v).lower() for v in (
                entry.get("original"), entry.get("original_rel"), fname
            ) if v)
            if any(k in hay for k in keywords):
                cands.append(fname)
        # 只保留磁盘上真实存在的
        cands = [c for c in sorted(cands)
                 if os.path.isfile(os.path.join(root, pool, c))
                 and os.path.join(root, pool, c) not in used]
        if not cands:
            gaps.append(f"{el} [池 {pool} 无匹配素材]")
            continue
        chosen = rng.choice(cands)
        path = os.path.join(root, pool, chosen)
        used.add(path)
        picks.append((pool, path, str(el), rule.get("why", "")))

    return picks, gaps


def known_keywords() -> list[str]:
    return sorted({str(k) for r in _load_rules() for k in r["match"]})
