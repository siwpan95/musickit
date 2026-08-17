"""曲式模板库测试 — 验证 structures.json 合法性与其解析逻辑。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


def _load():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "templates", "structures.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_templates_json_valid():
    data = _load()
    names = [k for k in data if not k.startswith("_")]
    assert len(names) >= 3
    for name in names:
        t = data[name]
        assert t.get("min_bars", 0) >= 1
        assert "layers" in t and t["layers"]
        for cat, (s, e) in t["layers"].items():
            assert s >= 0 and e != 0


def test_resolve_sections_min_bars():
    st = {"min_bars": 13, "fade_out_bars": 2, "layers": {"drum": [0, -1]}}
    assert main._resolve_sections(st, 8) == ({}, 0)   # 不足 min_bars → 全铺平
    secs, fade = main._resolve_sections(st, 16)
    assert fade == 2
    assert secs["drum"] == (0, 16)


def test_resolve_sections_negative_offsets():
    st = {"min_bars": 13, "fade_out_bars": 4,
          "layers": {"bass": [4, -4], "cowbell": [6, -6]}}
    secs, _ = main._resolve_sections(st, 32)
    assert secs["bass"] == (4, 28)
    assert secs["cowbell"] == (6, 26)


def test_load_structures_fallback():
    data = main._load_structures()
    assert "classic_drop" in data  # 内置兜底与文件模板都应有此模板


def test_intensity_curve_ramps():
    it = {"enter_db": -6.0, "exit_db": -8.0, "ramp_bars": 1}
    curve = main._intensity_curve(16, 4, 12, it)
    assert curve[4] == pytest.approx(-6.0)   # 进场首小节 = enter_db
    assert curve[11] == pytest.approx(-8.0)  # 退场末小节 = exit_db
    assert curve[8] == 0.0                   # 中间平直
    assert curve[0] == 0.0                   # 区间外无增益


def test_intensity_curve_ramp2():
    it = {"enter_db": -4.0, "exit_db": -10.0, "ramp_bars": 2}
    curve = main._intensity_curve(16, 0, 16, it)
    assert curve[0] == pytest.approx(-4.0)
    assert curve[1] == pytest.approx(-2.0)   # 第 2 小节过渡值
    assert curve[15] == pytest.approx(-10.0)
    assert curve[14] == pytest.approx(-5.0)
