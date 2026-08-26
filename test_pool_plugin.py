# -*- coding: utf-8 -*-
"""test_pool_plugin.py —— 采样池插件协议测试（musickit S5）"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pool_plugin import PoolRegistry, POOLS, REGISTRY_VERSION, count_tiers, validate_pool


def _fixture_root():
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    for pid in ("bass", "drum", "synth"):
        d = root / pid
        d.mkdir()
        (d / "manifest.json").write_text(
            json.dumps([
                {"file": "a.wav", "license_tier": "free"},
                {"file": "b.wav", "license_tier": "pack"},
                {"file": "c.wav", "license_tier": "restricted"},
                {"file": "d.wav", "license_tier": "unknown"},
                {"file": "e.wav", "license_tier": "free"},
            ]), encoding="utf-8")
    return root


def test_count_tiers_streaming():
    root = _fixture_root()
    stats = count_tiers(root / "bass" / "manifest.json")
    assert stats == {"free": 2, "pack": 1, "restricted": 1, "unknown": 1, "total": 5}


def test_register_dump_rollback():
    root = _fixture_root()
    reg = PoolRegistry(root=root)
    reg.register_all(["bass", "drum", "synth"])
    assert len(reg) == 3
    dump = {d["id"]: d for d in reg.dump()}
    assert dump["bass"]["release_safe"] == 3  # free 2 + pack 1
    assert dump["bass"]["total"] == 5
    assert reg.unregister("drum") is not None
    assert len(reg) == 2


def test_validate_fail_loud():
    root = _fixture_root()
    errs = validate_pool("not_exist", root)
    assert any("目录不存在" in e for e in errs)
    (root / "cowbell").mkdir()
    errs2 = validate_pool("cowbell", root)
    assert any("manifest.json 缺失" in e for e in errs2)
    assert validate_pool("bass", root) == []


def test_event_log():
    root = _fixture_root()
    tmp = tempfile.mkdtemp()
    log = Path(tmp) / "pool_events.log"
    reg = PoolRegistry(root=root, log_path=log)
    reg.register_all(["bass"])
    reg.log_scan(pools=1)
    e = json.loads(log.read_text(encoding="utf-8").strip().split("\n")[0])
    assert e["type"] == "pool_scan"
    assert {"seq", "ts", "type"} <= set(e)


def test_cli_dump_json():
    here = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "pool_plugin.py", "--dump", "--json"],
                       cwd=here, env=env, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert r.returncode == 0, r.stderr[-300:]
    data = json.loads(r.stdout)
    assert data["count"] == 13
    assert data["version"] == REGISTRY_VERSION
    assert data["problems"] == []
    assert set(p["id"] for p in data["pools"]) == set(POOLS)


def test_real_pools_summary():
    """真实 13 池全注册 + tier 聚合（流式扫描，不做量级断言）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    reg = PoolRegistry(root=Path(here))
    reg.register_all()
    assert len(reg) == 13
    for d in reg.dump():
        assert d["total"] >= 0
        assert d["release_safe"] == d["free"] + d["pack"]
