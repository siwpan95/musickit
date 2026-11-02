"""ingest_stems 的灌库契约测试（纯逻辑，不跑 demucs、不联网）。

锁住三件事：
  1. demucs 四轨 → 四个池的映射（drums/bass/other/vocals → drum/bass/guita/acapella）
  2. manifest 按 basename upsert，且写全 sha256 / duration_s / license
  3. 幂等：内容相同则跳过，不重复插入
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import ingest_stems as ing  # noqa: E402

pytestmark = pytest.mark.smoke


def _tone(path: str, freq: float = 220.0, dur: float = 1.0, sr: int = 44100) -> None:
    t = np.arange(int(sr * dur)) / sr
    sig = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.stack([sig, sig], axis=1), sr, subtype="PCM_16")


@pytest.fixture
def demucs_dir(tmp_path):
    """伪造 demucs 输出：<out>/htdemucs/<track>/{drums,bass,other,vocals}.wav"""
    base = tmp_path / "demucs_out"
    for kind, f in (("drums", 110), ("bass", 55), ("other", 330), ("vocals", 660)):
        _tone(str(base / "htdemucs" / "My Song" / f"{kind}.wav"), freq=f)
    return str(base)


@pytest.fixture
def mk_root(tmp_path):
    root = tmp_path / "musickit"
    for pool in ("drum", "bass", "guita", "acapella"):
        d = root / pool
        d.mkdir(parents=True)
        (d / "manifest.json").write_text('{"generated_by": "test", "entries": []}',
                                         encoding="utf-8")
    return str(root)


class TestSlugify:
    def test_keeps_cjk_strips_symbols(self):
        assert ing.slugify("Alls Fair In Love") == "Alls_Fair_In_Love"
        assert ing.slugify("夜曲 / Nocturne!") == "夜曲_Nocturne"

    def test_never_empty(self):
        assert ing.slugify("///") == "track"


class TestCollectStems:
    def test_finds_four_stems(self, demucs_dir):
        stems = ing.collect_stems(demucs_dir, "htdemucs")
        kinds = sorted(k for k, _, _ in stems)
        assert kinds == ["bass", "drums", "other", "vocals"]
        assert all(t == "My Song" for _, t, _ in stems)

    def test_empty_dir_returns_nothing(self, tmp_path):
        assert ing.collect_stems(str(tmp_path / "nope"), "htdemucs") == []


class TestIngest:
    def test_maps_each_stem_to_its_pool(self, demucs_dir, mk_root):
        stems = ing.collect_stems(demucs_dir, "htdemucs")
        stats = ing.ingest(stems, mk_root, "freepd", "CC0", "free", "freepd", dry_run=False)

        assert stats["insert"] == 4
        for pool in ("drum", "bass", "guita", "acapella"):
            files = [f for f in os.listdir(os.path.join(mk_root, pool)) if f.endswith(".wav")]
            assert files == ["freepd__My_Song.wav"], f"{pool} 落盘文件名不符"

    def test_manifest_written_with_required_fields(self, demucs_dir, mk_root):
        ing.ingest(ing.collect_stems(demucs_dir, "htdemucs"), mk_root,
                   "freepd", "CC0 1.0", "free", "freepd", dry_run=False)

        data = json.loads((open(os.path.join(mk_root, "drum", "manifest.json"),
                                encoding="utf-8")).read())
        assert len(data["entries"]) == 1
        e = data["entries"][0]
        for key in ("file", "source_pack", "original", "license", "duration_s",
                    "sha256", "subcategory", "content_kind"):
            assert key in e, f"manifest 缺字段 {key}"
        assert e["file"] == "freepd__My_Song.wav"
        assert e["content_kind"] == "stem"
        assert abs(e["duration_s"] - 1.0) < 0.05
        assert len(e["sha256"]) == 64

    def test_idempotent_second_run_skips(self, demucs_dir, mk_root):
        stems = ing.collect_stems(demucs_dir, "htdemucs")
        first = ing.ingest(stems, mk_root, "freepd", "CC0", "free", "freepd", dry_run=False)
        second = ing.ingest(stems, mk_root, "freepd", "CC0", "free", "freepd", dry_run=False)

        assert first["insert"] == 4
        assert second["skip_same"] == 4
        assert second["insert"] == 0
        data = json.loads(open(os.path.join(mk_root, "drum", "manifest.json"),
                               encoding="utf-8").read())
        assert len(data["entries"]) == 1, "重复灌库不应产生重复条目"

    def test_preserves_existing_entries(self, demucs_dir, mk_root):
        mpath = os.path.join(mk_root, "drum", "manifest.json")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump({"entries": [{"file": "old.wav", "license_tier": "unknown"}]}, f)

        ing.ingest(ing.collect_stems(demucs_dir, "htdemucs"), mk_root,
                   "freepd", "CC0", "free", "freepd", dry_run=False)

        data = json.loads(open(mpath, encoding="utf-8").read())
        names = [e["file"] for e in data["entries"]]
        assert "old.wav" in names, "既有条目被覆盖了"
        assert "freepd__My_Song.wav" in names

    def test_dry_run_touches_nothing(self, demucs_dir, mk_root):
        ing.ingest(ing.collect_stems(demucs_dir, "htdemucs"), mk_root,
                   "freepd", "CC0", "free", "freepd", dry_run=True)

        assert os.listdir(os.path.join(mk_root, "drum")) == ["manifest.json"]
        data = json.loads(open(os.path.join(mk_root, "drum", "manifest.json"),
                               encoding="utf-8").read())
        assert data["entries"] == []
