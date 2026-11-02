"""element_pool 的契约测试：氛围词 → 真实素材，不假映射。"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import element_pool as ep  # noqa: E402

pytestmark = pytest.mark.smoke


def _mk_pool(root: str, pool: str, files: dict[str, str]) -> dict:
    """建一个假池：{文件名: original 名}，并写 manifest。"""
    d = os.path.join(root, pool)
    os.makedirs(d, exist_ok=True)
    entries = {}
    for fname, original in files.items():
        t = np.arange(4410) / 44100
        sf.write(os.path.join(d, fname),
                 np.stack([0.2 * np.sin(2 * np.pi * 300 * t)] * 2, axis=1),
                 44100, subtype="PCM_16")
        entries[fname] = {"file": fname, "original": original}
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": list(entries.values())}, f, ensure_ascii=False)
    return {pool: entries}


@pytest.fixture
def pools(tmp_path):
    root = str(tmp_path)
    e = {}
    e.update(_mk_pool(root, "animal", {
        "animal (1).wav": "1212_Forest_birds_singing.wav",
        "animal (2).wav": "1775_Wolf_howling.wav",
        "animal (3).wav": "1780_Single_cricket_screech.wav",
        "animal (4).wav": "1744_Cow_moo.wav",
    }))
    e.update(_mk_pool(root, "sfx", {
        "sfx (1).wav": "1168_Woosh_wind.wav",
        "sfx (2).wav": "1279_Fast_thunder_impact.wav",
        "sfx (3).wav": "1489_Air_woosh.wav",
    }))
    return root, e


class TestResolve:
    def test_forest_maps_to_bird(self, pools):
        root, entries = pools
        picks, gaps = ep.resolve(["森林"], entries, root, random.Random(1))
        assert len(picks) == 1
        pool, path, element, why = picks[0]
        assert pool == "animal" and element == "森林"
        assert "bird" in os.path.basename(path).lower() or "animal (1)" in path
        assert why, "必须给出映射理由"

    def test_rain_maps_to_sfx(self, pools):
        root, entries = pools
        picks, _ = ep.resolve(["雨"], entries, root, random.Random(1))
        assert picks and picks[0][0] == "sfx"

    def test_unknown_element_goes_to_gaps(self, pools):
        root, entries = pools
        picks, gaps = ep.resolve(["量子物理"], entries, root)
        assert picks == []
        assert any("量子物理" in g and "无匹配规则" in g for g in gaps)

    def test_pool_without_matching_material_goes_to_gaps(self, pools):
        """规则命中但池里没有对应素材 → 记缺口，不能塞一条不相关的。"""
        root, entries = pools
        entries["animal"] = {}          # 清空 animal
        picks, gaps = ep.resolve(["狼"], entries, root)
        assert picks == []
        assert any("无匹配素材" in g for g in gaps)

    def test_max_accents_respected(self, pools):
        root, entries = pools
        picks, _ = ep.resolve(["森林", "狼", "虫", "雨"], entries, root,
                             random.Random(3), max_accents=2)
        assert len(picks) == 2

    def test_skip_avoids_duplicates(self, pools):
        root, entries = pools
        first, _ = ep.resolve(["狼"], entries, root, random.Random(1))
        used = {first[0][1]}
        second, gaps = ep.resolve(["狼"], entries, root, random.Random(1), skip=used)
        # animal (2) 被排除后仍有其它狼/动物文件可退，或进入 gaps
        assert all(p[1] not in used for p in second)

    def test_empty_elements(self, pools):
        root, entries = pools
        assert ep.resolve([], entries, root) == ([], [])
        assert ep.resolve(None, entries, root) == ([], [])

    def test_keywords_nonempty(self):
        kw = ep.known_keywords()
        assert "森林" in kw and "雨" in kw


class TestTable:
    def test_rules_are_wellformed(self):
        for r in ep._load_rules():
            assert r["match"] and r["pool"] in ("sfx", "animal")
            assert r.get("file_match"), "每条规则都要有素材过滤词，否则会乱选"
