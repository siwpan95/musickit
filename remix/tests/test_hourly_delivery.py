"""交付规格回读的三态语义：OK / 不合规 / 未校验。

真实现场：本机 `E:\\ffmpeg\\bin` 只有 ffmpeg.exe，没有 ffprobe.exe。
老代码在渲染**成功并落盘之后**调 `binfind.require("ffprobe")`，直接抛
`BinaryNotFound` —— 无人值守任务每跑一次都在收尾崩一次，索引也不写。
现在缺 ffprobe 只是「这一项没验」，不是任务失败。
"""
from __future__ import annotations

import os
import sys
import types

import pytest

_REMIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REMIX)
sys.path.insert(0, os.path.join(_REMIX, "tools"))

import hourly_remix as hr  # noqa: E402

pytestmark = pytest.mark.smoke

# 一份「应当合规」的实测结果：24bit/48k/立体声、码率够、体积正常、时长对得上
GOOD_INFO = {
    "codec": "pcm_s24le",
    "sample_rate": 48000,
    "bit_depth": 24,
    "channels": 2,
    "kbps": 2304.0,
    "size_mb": 1.88,
    "ffprobe_duration_s": 6.86,
}


class TestMissingFFprobeIsUnverified:
    def test_returns_none_verdict_instead_of_raising(self, monkeypatch):
        """缺 ffprobe 不能抛异常（老代码就是在这里崩的）。"""
        import core.binfind as binfind

        real = binfind.resolve
        monkeypatch.setattr(
            binfind, "resolve",
            lambda name: None if name == "ffprobe" else real(name))

        info, ok, reasons = hr.verify_delivery("whatever.wav", 3.0, 3.0, 200.0)

        assert ok is None, "未校验必须是 None —— 不能让调用方误当成失败"
        assert "error" in info
        assert any("ffprobe" in r for r in reasons)

class TestVerdictLabel:
    """三态必须映射成三个不同的词 —— 否则「未校验」会被读成「失败」。"""

    def test_three_states_have_distinct_labels(self):
        assert hr.delivery_verdict(True) == "OK"
        assert hr.delivery_verdict(False) == "FAIL"
        assert hr.delivery_verdict(None) == "UNVERIFIED"
        assert len({hr.delivery_verdict(True), hr.delivery_verdict(False),
                    hr.delivery_verdict(None)}) == 3

    def test_unverified_is_not_labelled_fail(self):
        assert hr.delivery_verdict(None) != hr.delivery_verdict(False)


class TestProbeResults:
    def test_compliant_delivery_passes(self, monkeypatch):
        import core.binfind as binfind

        monkeypatch.setattr(binfind, "resolve", lambda name: "ffprobe.exe")
        monkeypatch.setattr(hr, "probe_delivery", lambda path, exe: dict(GOOD_INFO))

        info, ok, reasons = hr.verify_delivery("ok.wav", 6.86, 1.0, 200.0)

        assert ok is True, f"应判合规，实际原因：{reasons}"
        assert reasons == []
        assert info["codec"] == "pcm_s24le"

    def test_low_bitrate_delivery_fails_with_reasons(self, monkeypatch):
        import core.binfind as binfind

        monkeypatch.setattr(binfind, "resolve", lambda name: "ffprobe.exe")
        bad = dict(GOOD_INFO, kbps=192.0, sample_rate=44100)
        monkeypatch.setattr(hr, "probe_delivery", lambda path, exe: bad)

        _info, ok, reasons = hr.verify_delivery("bad.wav", 6.86, 1.0, 200.0)

        assert ok is False
        assert any("码率" in r for r in reasons)
        assert any("采样率" in r for r in reasons)

    def test_probe_error_is_reported_not_swallowed(self, monkeypatch):
        import core.binfind as binfind

        monkeypatch.setattr(binfind, "resolve", lambda name: "ffprobe.exe")
        monkeypatch.setattr(hr, "probe_delivery",
                            lambda path, exe: {"probe_error": "decode failed"})

        _info, ok, reasons = hr.verify_delivery("x.wav", 6.86, 1.0, 200.0)

        assert ok is False
        assert any("ffprobe 失败" in r for r in reasons)
