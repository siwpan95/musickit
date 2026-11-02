"""tagging 的契约测试：`sentence` 能落进成品元数据并可读回。"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tagging import MAX_LEN, read_tags, write_tags  # noqa: E402

pytestmark = pytest.mark.smoke


def _wav(path: str, dur: float = 1.0, sr: int = 44100) -> str:
    t = np.arange(int(sr * dur)) / sr
    sig = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(path, np.stack([sig, sig], axis=1), sr, subtype="PCM_16")
    return path


class TestWriteTags:
    def test_wav_roundtrip(self, tmp_path):
        p = _wav(str(tmp_path / "a.wav"))
        res = write_tags(p, title="曲名", comment="雨夜霓虹，五声音阶", artist="musickit")

        assert res["ok"], res
        got = read_tags(p)
        assert got.get("comment") == "雨夜霓虹，五声音阶"
        assert got.get("title") == "曲名"
        assert got.get("artist") == "musickit"

    def test_long_comment_is_clipped(self, tmp_path):
        p = _wav(str(tmp_path / "b.wav"))
        write_tags(p, comment="长" * (MAX_LEN + 200))

        got = read_tags(p)
        assert len(got.get("comment", "")) <= MAX_LEN + 1
        assert got["comment"].endswith("…")

    def test_missing_file_does_not_raise(self, tmp_path):
        res = write_tags(str(tmp_path / "nope.wav"), comment="x")
        assert res["ok"] is False
        assert "missing" in (res["error"] or "")

    def test_no_fields_is_noop(self, tmp_path):
        p = _wav(str(tmp_path / "c.wav"))
        assert write_tags(p)["ok"] is False

    def test_only_comment(self, tmp_path):
        """最常用形态：只写 sentence。"""
        p = _wav(str(tmp_path / "d.wav"))
        res = write_tags(p, comment="只有注释")
        assert res["written"] == ["comment"]
        assert read_tags(p).get("comment") == "只有注释"
