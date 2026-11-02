"""导出前后断言（T0-4）：空音频 / 静音 / 时长异常 / 坏文件必须被拦住。

历史事故：`--bars -1` 曾产出 102 字节、0 帧的空 WAV，并照样打印「已保存至」+ exit 0；
`--release-safe` 把音轨剔空时会产出静音 WAV 同样报成功。本文件的用例锁住这两类。
"""
from __future__ import annotations

import os
import sys

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as mk  # noqa: E402

pytestmark = pytest.mark.smoke


def _tone(ms: int = 4000, db: float = -12.0) -> AudioSegment:
    return Sine(220).to_audio_segment(duration=ms).apply_gain(db)


class TestValidateMix:
    def test_normal_mix_passes(self):
        """4s @ 120BPM = 2 小节，正好匹配 → 通过。"""
        mk._validate_mix(_tone(4000), bpm=120, bars=2)

    def test_empty_mix_rejected(self):
        with pytest.raises(mk.MixValidationError, match="为空"):
            mk._validate_mix(AudioSegment.silent(duration=0), bpm=120, bars=2)

    def test_silent_mix_rejected(self):
        """静音（峰值 -inf）必须被拦住 —— 这是 release-safe 剔空的形态。"""
        with pytest.raises(mk.MixValidationError, match="静音"):
            mk._validate_mix(AudioSegment.silent(duration=4000), bpm=120, bars=2)

    def test_duration_mismatch_rejected(self):
        """8s 的音频声称 2 小节（4s）→ 超出容差，必须报时长异常。"""
        with pytest.raises(mk.MixValidationError, match="时长异常"):
            mk._validate_mix(_tone(8000), bpm=120, bars=2)

    def test_negative_bars_rejected(self):
        """--bars -1 的形态：期望时长为负，必须拦。"""
        with pytest.raises(mk.MixValidationError):
            mk._validate_mix(_tone(4000), bpm=120, bars=-1)


class TestVerifyExported:
    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(mk.MixValidationError, match="不存在"):
            mk._verify_exported(str(tmp_path / "nope.wav"), bpm=120, bars=2)

    def test_tiny_file_rejected_and_removed(self, tmp_path):
        """空容器（102 字节）必须报错并从磁盘删掉，不留假产物。"""
        bad = tmp_path / "empty.wav"
        bad.write_bytes(b"\x00" * 102)

        with pytest.raises(mk.MixValidationError, match="过小"):
            mk._verify_exported(str(bad), bpm=120, bars=2)
        assert not bad.exists()  # 已清理

    def test_real_export_passes(self, tmp_path):
        good = tmp_path / "ok.wav"
        _tone(4000).export(str(good), format="wav")

        mk._verify_exported(str(good), bpm=120, bars=2)
        assert good.exists()


class TestArgparseBounds:
    """参数下界：0 / 负数必须在 argparse 层拒绝（exit 2），不能进渲染。"""

    @pytest.mark.parametrize("value", ["0", "-1", "abc"])
    def test_bars_rejects_bad_values(self, value):
        with pytest.raises(Exception):
            mk._positive_int(value)

    @pytest.mark.parametrize("value", ["0", "-5", "401"])
    def test_bpm_rejects_out_of_range(self, value):
        with pytest.raises(Exception):
            mk._bpm_int(value)

    def test_valid_values_accepted(self):
        assert mk._positive_int("32") == 32
        assert mk._bpm_int("120") == 120
