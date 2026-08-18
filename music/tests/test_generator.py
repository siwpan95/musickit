"""music_prompt_generator 生成层单元测试（调式短语去重 / 种子可复现）。"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import music_prompt_generator as mpg  # noqa: E402


@pytest.mark.parametrize("scale,expected", [
    ("清乐调式", "，清乐调式"),
    ("五声音阶", "，五声音阶"),
    ("小调", "，小调"),
    ("多利亚", "，多利亚调式"),
    ("五声", "，五声调式"),
])
def test_scale_phrase_no_duplicate_suffix(scale, expected):
    assert mpg._scale_phrase(scale) == expected


def test_build_sentence_no_double_diao():
    # 场景先行模板：scale 已含「调式」时不得出现「调式调式」
    s = mpg._build_sentence("国风", "", ["鼓"], "清乐调式", [], "120 BPM", [], "")
    assert "清乐调式" in s
    assert "调式调式" not in s
    # 制作笔记模板不受影响
    s2 = mpg._build_sentence("国风", "", ["鼓"], "小调", [], "120 BPM", [], "")
    assert "小调调式" not in s2


def test_generate_seed_reproducible():
    random.seed(11)
    a = mpg.generate(mpg.STYLE_BY_KEY["phonk"])
    random.seed(11)
    b = mpg.generate(mpg.STYLE_BY_KEY["phonk"])
    assert a == b
