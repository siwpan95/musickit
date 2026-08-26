# -*- coding: utf-8 -*-
"""test_mixer_plugin.py —— 混音师插件协议测试（musickit S2）"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mixer_styles as ms
from mixer_plugin import MixerRegistry, validate_manifest, REGISTRY_VERSION


def test_24_plugins_register_and_dump():
    reg = MixerRegistry()
    reg.register_all(ms.STYLES)
    dump = reg.dump()
    assert len(reg) == 24, f"应注册 24 位混音师，实际 {len(reg)}"
    assert len(dump) == 24
    assert all(d["slug"] and d["name"] and d["zh"] for d in dump)
    assert dump[0]["slug"] == "albini"  # dump 按 slug 字母序
    assert {"burbidge", "albini", "ghenea"} <= set(reg.slugs)


def test_validate_fail_loud():
    bad = {"slug": "x", "name": "X", "zh": "某"}
    errs = validate_manifest(bad)
    assert any("drums" in e for e in errs)
    assert any("reverb" in e for e in errs)
    ok = validate_manifest(ms.STYLES[0])
    assert ok == []


def test_register_rollback():
    reg = MixerRegistry()
    reg.register_all(ms.STYLES)
    extra = dict(ms.STYLES[0])
    extra["slug"] = "temp-plugin"
    reg.register(extra)
    assert len(reg) == 25
    popped = reg.unregister("temp-plugin")
    assert popped is not None
    assert len(reg) == 24
    assert "temp-plugin" not in reg.slugs


def test_resolve_event_log():
    tmp = tempfile.mkdtemp()
    log_path = Path(tmp) / "mixer_events.log"
    reg = MixerRegistry(log_path=log_path)
    reg.register_all(ms.STYLES)
    style = reg.resolve("burbidge")
    assert style["slug"] == "burbidge"
    style2 = reg.resolve("random", rng=__import__("random").Random(42))
    assert style2["slug"] in reg.slugs
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    e0 = json.loads(lines[0])
    assert e0["type"] == "mixer_resolve"
    assert e0["style"] == "burbidge"
    assert {"seq", "ts", "type", "style", "name"} <= set(e0)


def test_resolve_semantics_match_styles():
    """行为与 mixer_styles.resolve_style 完全一致（无回归）。"""
    import random
    reg = MixerRegistry()
    reg.register_all(ms.STYLES)
    rng = random.Random(7)
    a = reg.resolve("random", rng=rng)
    rng2 = random.Random(7)
    b = ms.resolve_style("random", rng=rng2)
    assert a["slug"] == b["slug"]


def test_cli_dump_json():
    import subprocess
    r = subprocess.run([sys.executable, "mixer_plugin.py", "--dump", "--json"],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["count"] == 24
    assert data["version"] == REGISTRY_VERSION
    assert data["problems"] == []
