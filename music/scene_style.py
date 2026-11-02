"""scene_style — 把提示词的 `scene`（场景）映射到混音师签名链（架构文档 §7.3 第 3 项）。

为什么用规则表而不是穷举：生成器的 `scene` 实测有 **241 种**取值（都市夜景 / 纪录片配乐 /
时尚秀场 / 深夜独处 …），逐条指派 24 个混音师既不可能也不合理。这里只覆盖语义明确的
场景族，匹配不到就返回 None，由调用方保持原有行为（随机 / 显式指定）。

匹配依据是 `burbidge_album/mixer_styles.py` 里各风格的 `tagline`（如 wallace =
massive drums · arena loud），不是凭空指派 —— 词表在 `music/scene_styles.json`，
可随时改而不必动代码（与 `structure_moods.json` 同约定）。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_styles.json")


@lru_cache(maxsize=1)
def _load_rules() -> list[dict]:
    try:
        with open(_TABLE, encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules") or []
        return [r for r in rules if r.get("match") and r.get("slug")]
    except Exception:  # noqa: BLE001
        return []


def resolve(scene: str | None) -> tuple[str, str] | None:
    """scene 文本 → (mixer_slug, 理由)；无法判定返回 None。"""
    if not scene or not isinstance(scene, str):
        return None
    text = scene.strip().lower()
    if not text:
        return None
    for rule in _load_rules():
        for kw in rule["match"]:
            if str(kw).lower() in text:
                return rule["slug"], rule.get("why", "")
    return None


def known_slugs() -> list[str]:
    return sorted({r["slug"] for r in _load_rules()})
