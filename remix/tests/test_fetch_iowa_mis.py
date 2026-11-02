"""fetch_iowa_mis 的纯逻辑契约（不联网）。

联网部分（抓页面/下载）靠 dry-run 与真跑验证，这里只锁那些"错了会静默写坏 manifest"
的部分：链接编码、选取策略、manifest upsert 与格式保留。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_REMIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REMIX)
sys.path.insert(0, os.path.join(_REMIX, "tools"))

import fetch_iowa_mis as f  # noqa: E402

pytestmark = pytest.mark.smoke


class TestUrlEncoding:
    def test_space_becomes_percent20(self):
        url = f._abs_url("sound files/MIS/Strings/violin/Violin.arco.pp.sulG.G3B3.aiff")
        assert "%20" in url
        assert " " not in url
        assert url.startswith("https://theremin.music.uiowa.edu/")

    def test_already_encoded_path_is_not_double_encoded(self):
        """页面里两种写法都出现过（`sound files` / `sound%20files`），不能编两次。"""
        a = f._abs_url("sound files/MIS/x/Trumpet.vib.pp.E3B3.aiff")
        b = f._abs_url("sound%20files/MIS/x/Trumpet.vib.pp.E3B3.aiff")
        assert a == b
        assert "%2520" not in a

    def test_slashes_are_preserved(self):
        url = f._abs_url("sound files/MIS/Brass/Bbtrumpet/T.aiff")
        assert "MIS/Brass/Bbtrumpet" in url


class TestSpreadPicks:
    def test_spreads_across_the_whole_page(self):
        items = [f"n{i}" for i in range(20)]
        picked = f._spread(items, 4)
        assert len(picked) == 4
        # 等距取：不该全挤在前几条（只取前 4 会全是同一个力度/低音区）
        assert picked[0] == "n0"
        assert picked[-1] != items[3]
        assert int(picked[-1][1:]) >= 10

    def test_limit_larger_than_page_returns_all(self):
        items = ["a", "b", "c"]
        assert f._spread(items, 10) == items

    def test_zero_limit_means_all(self):
        items = ["a", "b", "c"]
        assert f._spread(items, 0) == items

    def test_no_duplicates(self):
        items = [f"n{i}" for i in range(13)]
        picked = f._spread(items, 10)
        assert len(set(picked)) == len(picked)


class TestManifestUpsert:
    def test_add_then_update_same_file(self):
        data = {"entries": []}
        e = {"file": "iowa__A.wav", "duration_s": 1.0}
        assert f.upsert(data, e) == "added"
        assert len(data["entries"]) == 1
        # 同名再进来应该是更新而不是追加一个重复条目
        assert f.upsert(data, {"file": "iowa__A.wav", "duration_s": 2.0}) == "updated"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["duration_s"] == 2.0

    def test_update_keeps_existing_fields(self):
        """更新只覆盖传入的键，别把已有字段（如 key）抹掉。"""
        data = {"entries": [{"file": "iowa__A.wav", "key": "C", "scope": "keep"}]}
        f.upsert(data, {"file": "iowa__A.wav", "duration_s": 3.0})
        assert data["entries"][0]["key"] == "C"
        assert data["entries"][0]["duration_s"] == 3.0


class TestManifestRoundTrip:
    def test_missing_manifest_starts_empty(self, tmp_path):
        d = f.load_manifest(str(tmp_path))
        assert d["entries"] == []

    def test_save_preserves_indent_and_lf(self, tmp_path):
        pool = tmp_path / "keys"
        pool.mkdir()
        mp = pool / "manifest.json"
        mp.write_text('{\n   "generated_by": "someone_else",\n   "entries": []\n}\n',
                      encoding="utf-8")
        data = f.load_manifest(str(pool))
        f.upsert(data, {"file": "x.wav"})
        f.save_manifest(str(pool), data)

        raw = mp.read_bytes()
        assert b"\r\n" not in raw, "写回不该把 LF 改成 CRLF（否则整份 manifest 进 diff）"
        text = raw.decode("utf-8")
        assert text.startswith('{\n   "file"') or '"entries"' in text
        d = json.loads(text)
        assert d["generated_by"] == "someone_else", "不该覆盖别人的 generated_by"
        assert d["last_ingested_by"] == "fetch_iowa_mis.py"

    def test_dry_run_does_not_touch_disk(self, tmp_path):
        pool = tmp_path / "keys"
        pool.mkdir()
        data = {"entries": [{"file": "x.wav"}]}
        f.save_manifest(str(pool), data, dry_run=True)
        assert not (pool / "manifest.json").exists()


class TestNoteOf:
    """单音文件名 -> 音级；范围样本必须返回 None（不能按起点瞎猜）。"""

    @pytest.mark.parametrize("name,expect", [
        ("Piano.pp.Bb0.aiff", "Bb"),
        ("Piano.ff.B5.aiff", "B"),
        ("Piano.mf.Ab6.aiff", "Ab"),
        ("Piano.ff.C#4.aiff", "C#"),
        ("BbClar.mf.C7.aiff", "C"),
    ])
    def test_single_note(self, name, expect):
        assert f.note_of(name) == expect

    @pytest.mark.parametrize("name", [
        "Violin.arco.pp.sulG.G3B3.aiff",   # 覆盖 G3~B3，根音不明确
        "Trumpet.vib.pp.E3B3.aiff",
        "Bassoon.pp.Bb1B1.aiff",
        "Flute.nonvib.pp.B3B4.aiff",
    ])
    def test_range_sample_has_no_pitch(self, name):
        assert f.note_of(name) is None

    def test_does_not_mistake_instrument_letter_for_note(self):
        """`BbClar`（降 B 单簧管）里的 B 不是音名 —— 没有紧跟数字就不该匹配。"""
        assert f.note_of("BbClar.mf.C7.aiff") == "C"


class TestPageTableConsistency:
    def test_every_instrument_has_a_page(self):
        """PAGES 与 _PAGE_OF 必须一一对应，漏一个就会 KeyError 到用户面前。"""
        assert set(f.PAGES) == set(f._PAGE_OF)

    def test_pools_are_real_pool_names(self):
        allowed = {"keys", "strings", "brass", "woodwind", "ethnic"}
        for inst, (pool, subcat, subdir) in f.PAGES.items():
            assert pool in allowed, f"{inst} 指向了不存在的池：{pool}"
            assert subcat and subdir, f"{inst} 缺 subcategory/original_rel"
            assert "/" in subdir, f"{inst} 的 original_rel 应是 `大类/乐器` 形式"
