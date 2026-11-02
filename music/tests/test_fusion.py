"""fusion 的契约测试：第二风格的招牌乐器必须真的被补进来。

背景：`generate(fusion_with=...)` 产出的 instruments 是混合池重采样，实测会丢掉主风格
的招牌乐器（新古典 × 中国民族乐器 → 竖琴/大提琴消失），所以「融合」只是换了一批乐器。
本模块验证桥接器显式补回第二风格乐器的逻辑。
"""
from __future__ import annotations

import os
import random
import sys

import numpy as np
import pytest
import soundfile as sf

_MUSIC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _MUSIC)

import prompt_driven_remix as pdr  # noqa: E402

pytestmark = pytest.mark.smoke


class TestFusionStyleLookup:
    def test_known_key_returns_label_and_instruments(self):
        label, insts = pdr._fusion_style_instruments("china_instr")
        assert label, "应能取到风格名"
        assert insts, "应能取到招牌乐器"
        assert any("古" in i or "笛" in i or "二胡" in i for i in insts)

    def test_unknown_key_returns_empty(self):
        assert pdr._fusion_style_instruments("no_such_style") == ("", [])
        assert pdr._fusion_style_instruments(None) == ("", [])
        assert pdr._fusion_style_instruments("") == ("", [])


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """只建 bass / drum 两个有素材的池（其它池为空，模拟当前仓库状态）。"""
    root = tmp_path / "mk"
    for pool in ("bass", "drum"):
        d = root / pool
        d.mkdir(parents=True)
        t = np.arange(44100) / 44100
        sig = (0.3 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
        sf.write(str(d / f"{pool} (1).wav"), np.stack([sig, sig], axis=1),
                 44100, subtype="PCM_16")
        (d / "manifest.json").write_text(
            '{"entries":[{"file":"%s (1).wav","duration_s":1.0,"license_tier":"free"}]}'
            % pool, encoding="utf-8")
    monkeypatch.setattr(pdr, "MUSICKIT_ROOT", str(root))
    return str(root)


def _base(**kw):
    d = {
        "label": "测试 × phonk", "subgenre": "x",
        "instruments": ["808 贝斯"], "bpm": "140", "scale": "小调",
        "moods": ["dark"], "scene": "派对热场", "sentence": "融合测试",
        "elements": [], "fusion": True, "fusion_with": "phonk",
    }
    d.update(kw)
    return d


class TestFusionAddsTracks:
    def test_fusion_on_adds_second_style_instruments(self, fake_root):
        mp = pdr.prompt_to_mix_params(_base(), random.Random(3))
        assert mp["fusion_added"], "融合应补进第二风格乐器"
        assert mp["fusion_label"], "应记录融合对象"

    def test_fusion_off_adds_nothing(self, fake_root):
        mp = pdr.prompt_to_mix_params(_base(fusion=False), random.Random(3))
        assert mp["fusion_added"] == []

    def test_no_duplicate_of_existing_instruments(self, fake_root):
        """第二风格的乐器若已在 instruments 里，不应重复添加。"""
        # phonk 的招牌乐器含 808 系；把它放进主列表后应被跳过
        _, insts = pdr._fusion_style_instruments("phonk")
        assert insts
        mp = pdr.prompt_to_mix_params(
            _base(instruments=[insts[0]]), random.Random(3))
        assert insts[0] not in mp["fusion_added"]

    def test_empty_pools_do_not_crash(self, tmp_path, monkeypatch):
        """池全空时融合补不进东西，但不能报错（当前仓库的 keys/strings 就是这种状态）。"""
        root = tmp_path / "empty"
        root.mkdir()
        monkeypatch.setattr(pdr, "MUSICKIT_ROOT", str(root))

        mp = pdr.prompt_to_mix_params(_base(), random.Random(3))
        assert mp["fusion_added"] == []


class TestFusionSurvivesTruncation:
    """回归：第 5 步裁剪从头部切，融合轨曾挂在尾部被静默截掉，而 fusion_added 照报"已补入"。

    `[remix] 已选择 5 条音轨` 那次的真实表现：dry-run 说补入 ['鼓组']，但引擎只收到 5 轨。
    """

    def test_fusion_track_is_added_not_swapped(self, fake_root, monkeypatch):
        """融合轨必须真的入轨，且不能顶替掉基础轨（否则又退化成"换乐器"）。

        基础轨只有 bass（808 贝斯），融合轨是 drum（鼓组），角色不同便于判别。
        """
        monkeypatch.setattr(pdr, "_fusion_style_instruments",
                            lambda _k: ("测试融合", ["鼓组"]))
        mp = pdr.prompt_to_mix_params(_base(), random.Random(3), max_tracks=1,
                                      add_skeleton=False)
        roles = [r for r, _ in mp["tracks"]]
        assert mp["fusion_added"] == ["鼓组"], "报告说补入就必须真补入"
        assert "drum" in roles, "融合轨没进 tracks → 假报告"
        assert "bass" in roles, "融合不该顶掉基础轨"

    def test_fusion_added_matches_actual_tracks(self, fake_root, monkeypatch):
        """fusion_added 必须 ≤ max_fusion_tracks，且每条都真的在 tracks 里留了轨。

        夹具只有 bass / drum 两池，所以「失真吉他」（guita 池）会被正确跳过——
        这正是"绝不假映射"的约束，报告里也不能出现它。
        """
        monkeypatch.setattr(pdr, "_fusion_style_instruments",
                            lambda _k: ("测试融合", ["808 Bass", "鼓组", "失真吉他"]))
        mp = pdr.prompt_to_mix_params(_base(), random.Random(3), max_tracks=2,
                                      max_fusion_tracks=3)
        added = mp["fusion_added"]
        assert added == ["808 Bass", "鼓组"], "guita 池无素材，不该报进 fusion_added"
        assert len(added) <= len(mp["tracks"])
        # 基础 2 轨 + 融合 2 轨，都该在（融合是额外并入，不是顶替）
        assert len(mp["tracks"]) == 4

    def test_total_tracks_never_exceed_engine_limit(self, fake_root, monkeypatch):
        """无论融合补多少，总轨数不得超过引擎上限 8。"""
        monkeypatch.setattr(pdr, "_fusion_style_instruments",
                            lambda _k: ("测试融合", ["808 Bass", "鼓组"] * 4))
        mp = pdr.prompt_to_mix_params(_base(elements=["雨声", "动物叫声"]),
                                      random.Random(3), max_tracks=8,
                                      max_fusion_tracks=8)
        assert len(mp["tracks"]) <= 8
