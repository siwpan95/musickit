"""scene → 混音师映射的契约测试。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scene_style as ss  # noqa: E402

pytestmark = pytest.mark.smoke


class TestResolve:
    @pytest.mark.parametrize("scene,slug", [
        ("都市夜景", "ali"),
        ("深夜独处", "shebib"),
        ("派对热场", "lordalge"),
        ("纪录片配乐", "schmitt"),
        ("冥想", "guzauski"),
        ("独立现场", "albini"),
        ("时尚秀场", "ghenea"),
        ("极限运动", "mikedean"),
        ("旅行 Vlog", "scheps"),
        ("华语抒情", "zhoutianche"),
    ])
    def test_known_scenes(self, scene, slug):
        r = ss.resolve(scene)
        assert r is not None, f"{scene} 应命中规则"
        assert r[0] == slug
        assert r[1], "必须给出理由，便于审计"

    def test_unknown_scene_returns_none(self):
        assert ss.resolve("量子物理") is None
        assert ss.resolve("完全没见过的场景") is None

    @pytest.mark.parametrize("val", [None, "", "   "])
    def test_empty_returns_none(self, val):
        assert ss.resolve(val) is None

    def test_case_insensitive_english(self):
        assert ss.resolve("VLOG BGM") is not None
        assert ss.resolve("lofi beats") is not None

    def test_substring_match(self):
        """场景常带修饰语（「深夜的城市街头」），必须能子串命中。"""
        assert ss.resolve("深夜的城市街头").__getitem__(0) == "shebib"


class TestTable:
    def test_all_slugs_are_real_mixers(self):
        """词表里的 slug 必须真实存在于 24 位混音师注册表，否则渲染时会报错。"""
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "burbidge_album"))
        import mixer_styles as ms

        for slug in ss.known_slugs():
            assert slug in ms.STYLE_BY_SLUG, f"未知混音师 slug：{slug}"

    def test_rules_have_match_and_slug(self):
        for r in ss._load_rules():
            assert isinstance(r.get("match"), list) and r["match"]
            assert r.get("slug")
