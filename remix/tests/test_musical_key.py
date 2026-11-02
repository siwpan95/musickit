"""T2-1 调性偏好：解析 + 兼容排序的契约测试（纯逻辑）。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import musical_key as mk  # noqa: E402

pytestmark = pytest.mark.smoke


class TestParseTarget:
    @pytest.mark.parametrize("text,expect", [
        ("Cm", (0, "minor")),
        ("C minor", (0, "minor")),
        ("A minor", (9, "minor")),
        ("F# major", (6, "major")),
        ("A小调", (9, "minor")),
        ("C", (0, "major")),          # 只有音名 → 默认大调
        ("Bb", (10, "major")),
    ])
    def test_full_key(self, text, expect):
        assert mk.parse_target(text) == expect

    @pytest.mark.parametrize("text,fam", [
        ("小调", "minor"),
        ("多利亚", "minor"),
        ("Dorian", "minor"),
        ("布鲁斯", "minor"),
        ("和声小调", "minor"),
        ("大调", "major"),
        ("大调明亮", "major"),
        ("混合利底亚", "major"),
    ])
    def test_mode_only(self, text, fam):
        """提示词的 scale 只有调式、无主音 → 主音为 None，mode 正确。"""
        t = mk.parse_target(text)
        assert t is not None
        assert t[0] is None, "调式名不应被解析出主音"
        assert t[1] == fam

    @pytest.mark.parametrize("text", ["五声", "无调性", "全音阶", "半音阶", "", None, "???"])
    def test_unparsable_means_no_preference(self, text):
        assert mk.parse_target(text) is None

    def test_english_word_not_mistaken_for_note(self):
        """「Dorian」含字母 d，不能被当成 D 调 —— 这是最容易被误判的形态。"""
        t = mk.parse_target("多利亚 Dorian")
        assert t is not None and t[0] is None, "把 Dorian 解析成 D 调是错的"


class TestRank:
    def test_same_key_best(self):
        assert mk.rank((0, "minor"), (0, "minor")) == mk.RANK_SAME

    def test_relative_major_minor(self):
        # C major ↔ A minor
        assert mk.rank((0, "major"), (9, "minor")) == mk.RANK_RELATIVE
        assert mk.rank((9, "minor"), (0, "major")) == mk.RANK_RELATIVE

    def test_fifths(self):
        assert mk.rank((0, "minor"), (7, "minor")) == mk.RANK_FIFTH   # C→G
        assert mk.rank((0, "minor"), (5, "minor")) == mk.RANK_FIFTH   # C→F

    def test_parallel(self):
        assert mk.rank((0, "major"), (0, "minor")) == mk.RANK_PARALLEL

    def test_incompatible(self):
        assert mk.rank((0, "major"), (1, "major")) == mk.RANK_INCOMPATIBLE  # 小二度
        assert mk.rank((0, "major"), (6, "major")) == mk.RANK_INCOMPATIBLE  # 三全音

    def test_unknown_is_neutral(self):
        assert mk.rank(None, (0, "minor")) == mk.RANK_FIFTH
        assert mk.rank((0, "minor"), None) == mk.RANK_FIFTH

    def test_mode_only_compares_colour(self):
        """主音未知时只比色彩：同为 minor 最好，major 次之（可接受）。"""
        assert mk.rank((None, "minor"), (0, "minor")) == mk.RANK_SAME
        assert mk.rank((None, "minor"), (0, "major")) == mk.RANK_PARALLEL
        assert mk.rank((None, "minor"), (None, "minor")) == mk.RANK_SAME


class TestFormat:
    def test_full_key(self):
        assert mk.format_target((9, "minor")) == "A minor"

    def test_mode_only(self):
        assert "minor" in mk.format_target((None, "minor"))
        assert "仅调式" in mk.format_target((None, "minor"))

    def test_none(self):
        assert mk.format_target(None) == "未指定"


class TestPreferOrdering:
    """引擎侧的取舍：返回 (兼容子集, 其余)，两者相加必须等于全部（不许丢素材）。"""

    def _entries(self):
        return {"guita": {
            "same.wav":    {"key": "C",  "scale": "minor", "key_confidence": 0.9},
            "fifth.wav":   {"key": "G",  "scale": "minor", "key_confidence": 0.9},
            "rel.wav":     {"key": "Eb", "scale": "major", "key_confidence": 0.9},
            "far.wav":     {"key": "F#", "scale": "major", "key_confidence": 0.9},
            "par.wav":     {"key": "C",  "scale": "major", "key_confidence": 0.9},
            "nokey.wav":   {},
            "lowconf.wav": {"key": "C",  "scale": "minor", "key_confidence": 0.01},
        }}

    def test_splits_into_compatible_and_rest(self):
        import main as mk_main

        files = ["far.wav", "nokey.wav", "fifth.wav", "same.wav",
                 "rel.wav", "par.wav", "lowconf.wav"]
        compat, rest, stats = mk_main._prefer_key_compatible(
            files, "guita", self._entries(), mk.parse_target("Cm"))

        # 不许丢素材
        assert sorted(compat + rest) == sorted(files)

        # 兼容子集 = 同调 + 关系调 + 五度（按优先级排序）
        assert compat[0] == "same.wav"       # C minor
        assert compat[1] == "rel.wav"        # Eb major = 关系大调
        assert compat[2] == "fifth.wav"      # G minor = 五度
        assert set(compat) == {"same.wav", "rel.wav", "fifth.wav"}

        # 其余：同主音(C major)、未知、低置信、不兼容
        assert set(rest) == {"par.wav", "nokey.wav", "lowconf.wav", "far.wav"}
        assert stats["same"] == 1 and stats["relative"] == 1 and stats["fifth"] == 1

    def test_no_target_means_no_preference(self):
        import main as mk_main

        compat, rest, stats = mk_main._prefer_key_compatible(
            ["b.wav", "a.wav"], "guita", {}, None)
        assert compat == []
        assert rest == ["b.wav", "a.wav"]     # 全部落到 rest，调用方会原样使用

    def test_all_incompatible_gives_empty_compat(self):
        """全部不兼容时 compat 为空 → 调用方放宽到 rest（不会选不出音）。"""
        import main as mk_main

        compat, rest, _ = mk_main._prefer_key_compatible(
            ["far.wav"], "guita", self._entries(), mk.parse_target("Cm"))
        assert compat == []
        assert rest == ["far.wav"]


class TestRankPitch:
    """单音素材只知音级、不知调式时的兼容度。

    真实现场：`Piano.ff.B5` 用 chroma 判成了 C#m（conf 0.38 / margin 0.05），
    高音区泛音把音级带偏；而文件名写着 B。所以单音走「只看音级」这条路。
    """

    def test_same_pitch_class_is_best(self):
        assert mk.rank_pitch(11, mk.parse_target("Bm")) == mk.RANK_SAME
        assert mk.rank_pitch(0, mk.parse_target("C major")) == mk.RANK_SAME

    def test_fifth_and_fourth(self):
        # B 相对 E：E(4)+7 = 11 → 纯五
        assert mk.rank_pitch(11, mk.parse_target("E")) == mk.RANK_FIFTH
        assert mk.rank_pitch(4, mk.parse_target("B")) == mk.RANK_FIFTH

    def test_other_pitches_are_usable_not_incompatible(self):
        """单个音能当经过音/延伸音，不该判成不兼容（否则误杀可用素材）。"""
        r = mk.rank_pitch(2, mk.parse_target("Bm"))
        assert r == mk.RANK_PARALLEL
        assert r != mk.RANK_INCOMPATIBLE

    def test_unknown_target_falls_back_to_fifth(self):
        assert mk.rank_pitch(11, None) == mk.RANK_FIFTH
        # 目标只有调式、没有主音 → 没法比音级
        assert mk.rank_pitch(11, (None, "minor")) == mk.RANK_FIFTH

    def test_none_pitch(self):
        assert mk.rank_pitch(None, mk.parse_target("C")) == mk.RANK_FIFTH


class TestPitchOnlyEntriesAreUsed:
    """带 key_pitch_only 的条目必须真正参与选音，不能被当成「未知」。"""

    def _entries(self):
        return {"keys": {
            "b.wav":  {"key": "B",  "key_pitch_only": True, "key_confidence": 1.0},
            "e.wav":  {"key": "E",  "key_pitch_only": True, "key_confidence": 1.0},
            "c.wav":  {"key": "C",  "key_pitch_only": True, "key_confidence": 1.0},
        }}

    def test_pitch_only_material_enters_compat_subset(self):
        import main as mk_main

        compat, rest, stats = mk_main._prefer_key_compatible(
            ["b.wav", "e.wav", "c.wav"], "keys", self._entries(), mk.parse_target("Bm"))
        # B 同音级、E 纯五度 → 进兼容子集；C 落在「可用不优先」
        assert "b.wav" in compat and "e.wav" in compat
        assert "c.wav" in rest
        assert stats["pitch_only"] == 3, "三条都应被识别为「仅音级」而非未知"
        assert stats["unknown"] == 0

    def test_pitch_only_wins_over_stale_scale(self):
        """key_pitch_only 必须优先于 scale —— 否则会拼出没人测过的调式。

        真实现场：`Piano.ff.B5` 文件名是 B，detect_keys 却按 chroma 写成 C#m；
        刷新元数据后条目变成 key=B + scale=minor + key_pitch_only=True，
        若读取侧先看 scale，就会被当成"B 小调"。
        """
        import main as mk_main

        entries = {"keys": {"x.wav": {"key": "B", "scale": "minor",
                                      "key_pitch_only": True, "key_confidence": 1.0}}}
        compat, rest, stats = mk_main._prefer_key_compatible(
            ["x.wav"], "keys", entries, mk.parse_target("B"))

        assert "x.wav" in compat, "应走音级判定（同音级＝最合），而不是被 scale 带到别处"
        assert stats["pitch_only"] == 1
        assert stats["same"] == 1
