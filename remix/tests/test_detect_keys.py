"""detect_keys 的两件事：打分逻辑对不对、缺 librosa 时提示能不能照做。

为什么要专门的用例：librosa 是可选依赖（连 numba/llvmlite，比引擎本身重得多），
很多人不会装。裸 `import librosa` 抛出来的 `ModuleNotFoundError` 看不出是
"可选没装" 还是 "环境坏了"，所以用它的人会以为整条链路坏了。
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_REMIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REMIX)
sys.path.insert(0, os.path.join(_REMIX, "tools"))

import detect_keys as dk  # noqa: E402

pytestmark = pytest.mark.smoke


class TestKrumhanslScoring:
    """_score_chroma 是纯 numpy 的，不碰 librosa —— 可以直接验。"""

    def test_c_major_triad_scores_c_major(self):
        # 强 C / E / G，弱其余 → 应判 C major
        chroma = np.array([1.0, 0.0, 0.6, 0.0, 0.7, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0])
        pc, mode, conf, margin = dk._score_chroma(chroma)
        assert (pc, mode) == (0, "major")
        assert conf > 0.5 and margin > 0

    def test_a_minor_triad_scores_a_minor(self):
        # 强 A / C / E → A minor（pc=9）
        chroma = np.array([1.0, 0.0, 0.9, 0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        pc, mode, conf, margin = dk._score_chroma(chroma)
        assert mode == "minor"
        assert pc == 9

    def test_flat_chroma_has_near_zero_confidence(self):
        """均匀分布没有调性感，置信度应接近 0（margin 也在噪声级）。"""
        chroma = np.ones(12)
        _pc, _mode, conf, margin = dk._score_chroma(chroma)
        assert abs(conf) < 0.2
        assert margin < 0.2

    def test_scores_are_normalised_correlation(self):
        """Pearson 相关 → 置信度必须落在 [-1, 1]，否则阈值判断全失效。"""
        rng = np.random.default_rng(7)
        for _ in range(20):
            chroma = rng.random(12)
            _pc, _mode, conf, _margin = dk._score_chroma(chroma)
            assert -1.0 <= conf <= 1.0


class TestMissingLibrosa:
    """librosa 没装时必须给"照做就能修"的提示，而不是裸 ModuleNotFoundError。"""

    def test_need_librosa_explains_how_to_install(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "librosa", None)   # None → import 抛 ImportError
        with pytest.raises(SystemExit) as ei:
            dk._need_librosa()
        msg = str(ei.value)
        assert "requirements-keys.txt" in msg, "没给出安装命令，使用者不知道该装什么"
        assert "渲染混音本身不需要" in msg, "没说清这是可选依赖，会误判成整条链路坏了"

    def test_estimate_key_propagates_the_hint(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "librosa", None)
        with pytest.raises(SystemExit) as ei:
            dk.estimate_key("whatever.wav")
        assert "requirements-keys.txt" in str(ei.value)

    def test_need_librosa_returns_module_when_present(self):
        pytest.importorskip("librosa")      # 本机没装就跳过，不误报失败
        mod = dk._need_librosa()
        assert hasattr(mod, "feature")
