"""prompt_driven_remix 桥接器单元测试。

覆盖：乐器词映射（词长优先/无匹配/无样本）、曲式模板规则（外置 JSON）、
提示词归一化（扁平/结构化）、JSON 载入（数组/包裹对象）、
prompt_to_mix_params（角色去重/骨架兜底/BPM 钳制/gaps）、旋律层 loop 偏好。

测试不依赖真实素材库：map_instrument 用小型 fixture 分类体系，
文件收集与选音函数一律 monkeypatch。
"""
import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompt_driven_remix as pdr  # noqa: E402

FIX_WORD_MAP = {
    "808 贝斯": "808_bass",
    "贝斯": "bass_guitar",
    "鼓": "drums_acoustic",
    "牛铃 Cowbell": "cowbell",
    "人声切片": "vocal_chop",
    "巴乌": "woodwind",
    "钢琴": "keys_piano",
    "手风琴": "accordion",
    "无样本乐器": "ghost_class",
}
FIX_CLASSES = {
    "808_bass": {"pool": "bass", "available": True, "mixer_role": "bass"},
    "bass_guitar": {"pool": "bass", "available": True, "mixer_role": "bass"},
    "drums_acoustic": {"pool": "drum", "available": True, "mixer_role": "drum"},
    "cowbell": {"pool": "cowbell", "available": True, "mixer_role": "cowbell"},
    "vocal_chop": {"pool": "acapella", "available": True, "mixer_role": "vocal"},
    "woodwind": {"pool": "woodwind", "available": True, "mixer_role": "woodwind"},
    "keys_piano": {"pool": "keys", "available": True, "mixer_role": "keys"},
    "accordion": {"pool": "keys", "available": True, "mixer_role": "keys"},
    "ghost_class": {"pool": None, "available": False, "mixer_role": "synth"},
}


@pytest.fixture
def tax(monkeypatch):
    monkeypatch.setattr(pdr, "_WORD_MAP", dict(FIX_WORD_MAP))
    monkeypatch.setattr(pdr, "_CLASSES", FIX_CLASSES)
    monkeypatch.setattr(pdr, "_WORDS_BY_LEN",
                        sorted(FIX_WORD_MAP.keys(), key=len, reverse=True))


@pytest.fixture
def no_io(monkeypatch):
    monkeypatch.setattr(pdr, "_pool_entries", lambda: {})
    monkeypatch.setattr(pdr, "pick_loop_candidate",
                        lambda files, bpm, rng, entries=None: files[0] if files else None)
    monkeypatch.setattr(pdr, "_m_filter_release_safe",
                        lambda files, cat, entries, dropped: files)


def test_map_instrument_longest_first(tax):
    assert pdr.map_instrument("808 贝斯")["class"] == "808_bass"
    assert pdr.map_instrument("贝斯")["class"] == "bass_guitar"


def test_map_instrument_unknown_none(tax):
    assert pdr.map_instrument("不存在乐器") is None


def test_map_instrument_unavailable(tax):
    m = pdr.map_instrument("无样本乐器")
    assert m is not None and m["available"] is False


def test_choose_structure_rules():
    assert pdr.choose_structure("氛围音乐", "", ["梦幻"]) == "ambient_ghost"
    assert pdr.choose_structure("Phonk", "Drift", ["狂躁"]) == "classic_drop"
    assert pdr.choose_structure("Lo-Fi", "", ["慵懒"]) == "loop_stack"
    assert pdr.choose_structure("国风", "", ["空灵"]) == "classic_drop"  # 默认


def test_structure_moods_json_shape():
    rules = json.load(open(pdr._STRUCTURE_RULES_PATH, encoding="utf-8"))
    assert rules["order"] == ["ambient_ghost", "classic_drop", "loop_stack"]
    assert rules["default"] in rules["order"]


def test_normalize_prompt_flat():
    entry = {"style": "Phonk", "subgenre": "Drift",
             "instruments": "牛铃 Cowbell、808 贝斯", "moods": "暗黑、狂躁",
             "bpm": "135 BPM", "prompt": "一句提示词", "fusion": False,
             "fusion_with": ""}
    d = pdr._normalize_prompt(entry)
    assert d["label"] == "Phonk"
    assert d["instruments"] == ["牛铃 Cowbell", "808 贝斯"]
    assert d["moods"] == ["暗黑", "狂躁"]


def test_normalize_prompt_structured():
    d = pdr._normalize_prompt({"label": "X", "instruments": ["鼓"], "bpm": "120 BPM"})
    assert d["instruments"] == ["鼓"]


def test_load_prompts_from_json_array_and_wrapped(tmp_path):
    arr = [{"style": "A", "instruments": "鼓", "bpm": "120 BPM",
            "prompt": "p", "fusion": False, "fusion_with": ""}]
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps(arr, ensure_ascii=False), encoding="utf-8")
    assert len(pdr.load_prompts_from_json(str(p1))) == 1
    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps({"prompts": arr}, ensure_ascii=False), encoding="utf-8")
    assert len(pdr.load_prompts_from_json(str(p2))) == 1


def test_prompt_to_mix_params_roles_and_skeleton(tax, no_io, monkeypatch):
    def fake_collect(pool):
        return [f"G:/fake/{pool}/f_{i}.wav" for i in range(3)]
    monkeypatch.setattr(pdr, "collect_for_pool", fake_collect)
    data = {"label": "Phonk", "subgenre": "Drift", "moods": ["狂躁"],
            "bpm": "135 BPM", "instruments": ["鼓", "人声切片"]}
    mp = pdr.prompt_to_mix_params(data, random.Random(1))
    roles = [c for c, _ in mp["tracks"]]
    assert "drum" in roles and "vocal" in roles
    assert "bass" in roles          # 骨架兜底
    assert mp["bpm"] == 135
    assert mp["structure"] == "classic_drop"
    assert mp["gaps"] == []


def test_prompt_to_mix_params_role_dedup_and_gaps(tax, no_io, monkeypatch):
    def fake_collect(pool):
        return [f"G:/fake/{pool}/f.wav"]
    monkeypatch.setattr(pdr, "collect_for_pool", fake_collect)
    data = {"label": "X", "subgenre": "", "moods": [],
            "bpm": "100 BPM",
            "instruments": ["808 贝斯", "贝斯", "无样本乐器", "不存在乐器"]}
    mp = pdr.prompt_to_mix_params(data, random.Random(1))
    assert sum(1 for c, _ in mp["tracks"] if c == "bass") == 1  # 角色去重
    assert any("无样本乐器" in g for g in mp["gaps"])
    assert any("不存在乐器" in g for g in mp["gaps"])


def test_prompt_to_mix_params_bpm_clamp(tax, no_io, monkeypatch):
    monkeypatch.setattr(pdr, "collect_for_pool", lambda pool: ["G:/f.wav"])
    data = {"label": "X", "subgenre": "", "moods": [], "bpm": "300 BPM",
            "instruments": ["鼓"]}
    assert pdr.prompt_to_mix_params(data, random.Random(1))["bpm"] == 200
    data2 = {"label": "X", "subgenre": "", "moods": [], "bpm": "40 BPM",
             "instruments": ["鼓"]}
    assert pdr.prompt_to_mix_params(data2, random.Random(1))["bpm"] == 70


@pytest.fixture
def fix_classes_with_subs():
    cls = dict(FIX_CLASSES)
    cls["woodwind"] = {"pool": "woodwind", "available": True,
                       "mixer_role": "woodwind", "prefer_subdirs": ["woodwind"]}
    cls["keys_piano"] = {"pool": "keys", "available": True,
                         "mixer_role": "keys", "prefer_subdirs": ["piano"]}
    return cls


def test_map_instrument_returns_prefer_subdirs(tax, monkeypatch):
    cls = dict(FIX_CLASSES)
    cls["woodwind"] = {"pool": "woodwind", "available": True,
                       "mixer_role": "woodwind", "prefer_subdirs": ["woodwind"]}
    monkeypatch.setattr(pdr, "_CLASSES", cls)
    m = pdr.map_instrument("巴乌")
    assert m["prefer_subdirs"] == ["woodwind"]


def test_prefer_subdirs(monkeypatch, tmp_path):
    monkeypatch.setattr(pdr, "MUSICKIT_ROOT", str(tmp_path))
    (tmp_path / "woodwind" / "flute").mkdir(parents=True)
    (tmp_path / "woodwind" / "woodwind").mkdir()
    flute_file = str(tmp_path / "woodwind" / "flute" / "note_D3.wav")
    piece_file = str(tmp_path / "woodwind" / "woodwind" / "full_piece.mp3")
    out = pdr._prefer_subdirs([flute_file, piece_file], "woodwind", ["woodwind"])
    assert out == [piece_file]
    # 无命中 → 全量回退
    out2 = pdr._prefer_subdirs([flute_file], "woodwind", ["missing_dir"])
    assert out2 == [flute_file]


def test_loop_preferring_content_kind():
    files = ["a.wav", "b.wav", "c.wav"]
    entries = {"a.wav": {"content_kind": "single_note"},
               "b.wav": {"content_kind": "loop"},
               "c.wav": {"content_kind": "one_shot"}}
    assert pdr._loop_preferring(files, entries) == ["b.wav"]
    # 无 entries → 回退旧行为（非单音优先，此时全保留）
    assert len(pdr._loop_preferring(files, None)) == 3


def test_loop_preferring():
    files = ["EHn_susDyn_1-127_D3 - Group 1.wav", "SRHS_110_A_Koto_Loop_04.wav",
             "plain_hit.wav"]
    assert pdr._loop_preferring(files) == ["SRHS_110_A_Koto_Loop_04.wav"]
    files2 = ["EHn_susDyn_1-127_D3 - Group 1.wav", "plain_hit.wav"]
    assert pdr._loop_preferring(files2) == ["plain_hit.wav"]
    files3 = ["EHn_susDyn_1-127_D3 - Group 1.wav"]
    assert pdr._loop_preferring(files3) == files3
