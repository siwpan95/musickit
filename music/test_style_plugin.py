# -*- coding: utf-8 -*-
"""test_style_plugin.py —— 风格池插件协议测试（musickit S3）"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from style_plugin import StyleRegistry, validate_style, REGISTRY_VERSION, STYLES_DIR


def test_63_styles_register_and_dump():
    reg = StyleRegistry()
    reg.load_all()
    assert len(reg) == 63, f"应注册 63 个流派，实际 {len(reg)}"
    dump = reg.dump()
    assert len(dump) == 63
    assert all(d["key"] and d["label"] and d["bpm"] for d in dump)
    assert {"phonk", "lofi", "afrobeat"} <= set(reg.keys)


def test_validate_fail_loud():
    bad = {"key": "x", "label": "X"}
    errs = validate_style(bad)
    assert any("bpm" in e for e in errs)
    assert any("subgenres" in e for e in errs)
    import json as _j
    first = _j.loads((STYLES_DIR / "phonk.json").read_text(encoding="utf-8"))
    assert validate_style(first) == []


def test_register_rollback_and_dup():
    reg = StyleRegistry()
    reg.load_all()
    extra = {"key": "temp-style", "label": "临时", "bpm": "120 BPM", "subgenres": [{"name": "x", "bpm": "120 BPM"}]}
    reg.register(extra)
    assert len(reg) == 64
    assert reg.unregister("temp-style") is not None
    assert len(reg) == 63
    reg.register(extra)
    try:
        reg.register(extra)
        assert False, "重复 key 应报错"
    except ValueError as e:
        assert "重复" in str(e)


def test_pick_event_log():
    tmp = tempfile.mkdtemp()
    log = Path(tmp) / "prompt_events.log"
    reg = StyleRegistry(log_path=log)
    reg.load_all()
    reg.log_pick("phonk", source="bridge")
    lines = log.read_text(encoding="utf-8").strip().split("\n")
    e = json.loads(lines[0])
    assert e["type"] == "style_pick"
    assert e["key"] == "phonk"
    assert {"seq", "ts", "type", "key", "source"} <= set(e)


def test_cli_dump_json():
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "style_plugin.py", "--dump", "--json"],
                       cwd=here, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["count"] == 63
    assert data["version"] == REGISTRY_VERSION
    assert data["problems"] == []


def test_bridge_declarative_entry():
    """桥接器声明式入口：--list-styles 与未知 -c fail-loud。"""
    here = os.path.dirname(os.path.abspath(__file__))
    r1 = subprocess.run([sys.executable, "prompt_driven_remix.py", "--list-styles"],
                        cwd=here, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r1.returncode == 0, r1.stderr
    assert "63 个风格插件" in r1.stdout
    r2 = subprocess.run([sys.executable, "prompt_driven_remix.py", "-c", "not_a_style_x"],
                        cwd=here, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r2.returncode == 2
    assert "未知风格 key" in r2.stderr
