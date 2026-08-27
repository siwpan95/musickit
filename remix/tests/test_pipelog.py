# -*- coding: utf-8 -*-
"""
test_pipelog.py —— musickit remix 任务日志冒烟（与 WorldLog 同构模板）
"""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipelog import PipelineLog


def test_append_read():
    with tempfile.TemporaryDirectory() as tmp:
        log = PipelineLog(os.path.join(tmp, "pipeline.log"))
        log.append("run_start", run_id="r1", count=3, seed=42)
        log.append("stage_done", stage="remix", run_id="r1", output="out.wav")
        entries = log.read()
        assert len(entries) == 2
        assert entries[0]["type"] == "run_start" and entries[0]["seed"] == 42
        assert entries[1]["stage"] == "remix"
    print("[OK] 追加/读取")


def test_seq_continues():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "p.log")
        PipelineLog(p).append("run_start", run_id="r1")
        e = PipelineLog(p).append("run_end", run_id="r1", ok=True)
        assert e["seq"] == 2
    print("[OK] 序号续写")


def test_empty_when_no_file():
    with tempfile.TemporaryDirectory() as tmp:
        assert PipelineLog(os.path.join(tmp, "missing.log")).read() == []
    print("[OK] 无文件返回空")


if __name__ == "__main__":
    test_append_read()
    test_seq_continues()
    test_empty_when_no_file()
    print("\n✅ pipelog 冒烟全过")
