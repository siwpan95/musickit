"""查重工具链测试——守护「重名 ≠ 重复」原则。

覆盖：
  - dedupe_scan：同内容不同名 → 重复；同名不同内容 → 非重复；manifest sha256 不参与判重
  - dedupe_to_archive_v2：entry_identity（(subcategory, 文件名) 身份）、plan 保留规则
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools"))

import dedupe_scan  # noqa: E402
import dedupe_to_archive_v2 as dv2  # noqa: E402


def _write_bytes(root: str, rel: str, data: bytes) -> str:
    p = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return p


def test_scan_same_content_different_names(tmp_path):
    """同内容、不同名 → 判重。"""
    root = tmp_path / "musickit"
    (root / "drum").mkdir(parents=True)
    a = _write_bytes(str(root), "drum/a.wav", b"FAKE" * 1000)
    b = _write_bytes(str(root), "drum/b.wav", b"FAKE" * 1000)
    # 两份文件内容一致；manifest 故意给 a 记一个错误 sha256，验证其不参与判重
    with open(root / "drum" / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({"entries": [
            {"file": "a.wav", "sha256": "deadbeef"},
            {"file": "b.wav", "sha256": "deadbeef"},
        ]}, f)
    out = tmp_path / "report.json"
    sys.argv = ["dedupe_scan.py", "--root", str(root), "--out", str(out)]
    dedupe_scan.main()
    report = json.load(open(out, encoding="utf-8"))
    assert report["duplicate_groups"] == 1
    rels = sorted(m["rel"] for m in report["groups"][0]["members"])
    assert rels == ["drum/a.wav", "drum/b.wav"]
    # 错误的 manifest sha256 被交叉核对标记为 stale，但未影响判重结论
    assert any(x["rel"] == "drum/a.wav" for x in report["stale_manifest_hashes"])


def test_scan_same_name_different_content(tmp_path):
    """同名、不同内容（不同子目录）→ 非重复。"""
    root = tmp_path / "musickit"
    (root / "keys" / "piano").mkdir(parents=True)
    (root / "keys" / "rhodes").mkdir(parents=True)
    _write_bytes(str(root), "keys/piano/kick.wav", b"A" * 4000)
    _write_bytes(str(root), "keys/rhodes/kick.wav", b"B" * 4000)
    out = tmp_path / "report.json"
    sys.argv = ["dedupe_scan.py", "--root", str(root), "--out", str(out)]
    dedupe_scan.main()
    report = json.load(open(out, encoding="utf-8"))
    assert report["duplicate_groups"] == 0
    assert report["duplicate_files"] == 0


def test_scan_same_name_same_size_diff_tail(tmp_path):
    """同名同大小、仅尾部不同 → 候选签名碰撞但全量复核后非重复。"""
    root = tmp_path / "musickit"
    (root / "synth").mkdir(parents=True)
    data_a = b"C" * 20000 + b"TAIL-A"
    data_b = b"C" * 20000 + b"TAIL-B"
    assert len(data_a) == len(data_b)
    _write_bytes(str(root), "synth/lead.wav", data_a)
    _write_bytes(str(root), "synth/lead_2.wav", data_b)
    out = tmp_path / "report.json"
    sys.argv = ["dedupe_scan.py", "--root", str(root), "--out", str(out)]
    dedupe_scan.main()
    report = json.load(open(out, encoding="utf-8"))
    assert report["duplicate_groups"] == 0


def test_entry_identity():
    assert dv2.entry_identity("drum/drums_acoustic/drum (1).wav") == \
        ("drums_acoustic", "drum (1).wav")
    assert dv2.entry_identity("cowbell/cowbell (1).mp3") == ("(root)", "cowbell (1).mp3")
    assert dv2.entry_identity("acapella/vocal_chops/Pack/x.mp3") == \
        ("vocal_chops/Pack", "x.mp3")
    # 同名不同子目录 → 不同身份
    assert dv2.entry_identity("keys/piano/kick.wav") != dv2.entry_identity("keys/rhodes/kick.wav")


def test_plan_keeps_one_per_pool_per_group():
    report = {"groups": [{"size": 100, "sha256": "x", "members": [
        {"pool": "drum", "rel": "drum/hit.wav", "size": 100},
        {"pool": "drum", "rel": "drum/copy.wav", "size": 100},
        {"pool": "bass", "rel": "bass/also.wav", "size": 100},
    ]}]}
    moves = dv2.plan(report)
    rels = [m[1] for m in moves]
    assert rels == ["drum/hit.wav"]     # 同池保留字典序最小者（drum/copy.wav），其余被移
    assert "bass/also.wav" not in rels  # 跨池各留 1 份
