"""main.py 选音逻辑测试 — 骨架层保底选 loop / release-safe 过滤 / 输出命名防覆盖。

纯逻辑用例标记 @pytest.mark.smoke（无 ffmpeg 依赖，秒级跑完）；
run_remix 集成用例依赖 ffmpeg 编解码，不标记 smoke。
"""
import array
import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
from pydub import AudioSegment  # noqa: E402


def make_tone(ms: int, freq: int = 440) -> AudioSegment:
    """生成正弦波测试音频（不依赖 pydub.generators，兼容所有 pydub 版本）。"""
    n = int(44100 * ms / 1000)
    samples = array.array(
        "h", (int(30000 * math.sin(2 * math.pi * freq * i / 44100)) for i in range(n))
    )
    mono = AudioSegment(
        samples.tobytes(), frame_rate=44100, sample_width=2, channels=1
    )
    return mono.set_channels(2)


def write_wav(seg: AudioSegment, path: str) -> str:
    seg.export(path, format="wav")
    return path


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """构造只有音频文件（无 manifest）的假 musickit 根目录。"""
    root = tmp_path / "musickit"
    for cat in ["bass", "drum", "guita", "cowbell", "synth", "animal", "sfx"]:
        (root / cat).mkdir(parents=True)
    monkeypatch.setattr(main, "_MUSICKIT_ROOT", str(root))
    return root


@pytest.mark.smoke
def test_pick_loop_candidate_prefers_manifest_long(fake_root):
    drum = fake_root / "drum"
    write_wav(make_tone(300), str(drum / "short_hit.wav"))
    write_wav(make_tone(5000), str(drum / "long_loop.wav"))
    files = [str(drum / "short_hit.wav"), str(drum / "long_loop.wav")]
    entries = {
        "short_hit.wav": {"duration_s": 0.3},
        "long_loop.wav": {"duration_s": 5.0},
    }
    picked = main.pick_loop_candidate(files, 120, random.Random(1), entries)
    assert picked == str(drum / "long_loop.wav")


@pytest.mark.smoke
def test_pick_loop_candidate_probes_stems_first(fake_root):
    drum = fake_root / "drum"
    write_wav(make_tone(5000), str(drum / "drum (12).wav"))
    write_wav(make_tone(300), str(drum / "drum (13).wav"))
    write_wav(make_tone(300), str(drum / "noise_hit.wav"))
    files = [str(drum / "noise_hit.wav"), str(drum / "drum (13).wav"),
             str(drum / "drum (12).wav")]
    picked = main.pick_loop_candidate(files, 120, random.Random(1), None)
    assert picked == str(drum / "drum (12).wav")


@pytest.mark.smoke
def test_pick_loop_candidate_fallback_returns_best(fake_root):
    drum = fake_root / "drum"
    write_wav(make_tone(300), str(drum / "hit_a.wav"))
    write_wav(make_tone(500), str(drum / "hit_b.wav"))
    files = [str(drum / "hit_a.wav"), str(drum / "hit_b.wav")]
    picked = main.pick_loop_candidate(files, 120, random.Random(1), None)
    assert picked is not None
    assert picked in files


@pytest.mark.smoke
@pytest.mark.smoke
def test_pick_loop_candidate_null_duration(fake_root):
    """manifest duration_s 为 null（sync 条目常见）时不崩溃、走探测回退。"""
    drum = fake_root / "drum"
    write_wav(make_tone(5000), str(drum / "hit.wav"))
    files = [str(drum / "hit.wav")]
    entries = {"hit.wav": {"duration_s": None}}
    picked = main.pick_loop_candidate(files, 120, random.Random(1), entries)
    assert picked == files[0]


def test_pick_loop_candidate_empty():
    assert main.pick_loop_candidate([], 120, random.Random(1)) is None


@pytest.mark.smoke
def test_pick_random_tracks_skeleton_loopable(fake_root):
    drum = fake_root / "drum"
    for i in range(3):
        write_wav(make_tone(300), str(drum / f"hit_{i}.wav"))
    write_wav(make_tone(5000), str(drum / "drum (99).wav"))
    bass = fake_root / "bass"
    write_wav(make_tone(400), str(bass / "sub_hit.wav"))
    guita = fake_root / "guita"
    write_wav(make_tone(400), str(guita / "pluck.wav"))
    tracks = main._pick_random_tracks(3, seed=7, bpm=120)
    cats = [c for c, _ in tracks]
    assert cats == ["drum", "bass", "guita"]           # 骨架各 1 条
    drum_path = dict(tracks)["drum"]
    assert os.path.basename(drum_path) == "drum (99).wav"  # 长 loop 而非 one-shot


@pytest.mark.smoke
def test_pick_random_tracks_release_safe_filters(fake_root):
    drum = fake_root / "drum"
    write_wav(make_tone(5000), str(drum / "drum (1).wav"))
    (drum / "manifest.json").write_text(
        '{"entries": [{"file": "drum (1).wav", "license_tier": "restricted"}]}',
        encoding="utf-8",
    )
    bass = fake_root / "bass"
    write_wav(make_tone(5000), str(bass / "bass (1).wav"))
    (bass / "manifest.json").write_text(
        '{"entries": [{"file": "bass (1).wav", "license_tier": "free"}]}',
        encoding="utf-8",
    )
    guita = fake_root / "guita"
    write_wav(make_tone(5000), str(guita / "guita (1).wav"))
    (guita / "manifest.json").write_text(
        '{"entries": [{"file": "guita (1).wav", "license_tier": "pack"}]}',
        encoding="utf-8",
    )
    entries = main._load_pool_manifests(str(fake_root))
    tracks = main._pick_random_tracks(3, seed=7, bpm=120, entries=entries,
                                      release_safe=True)
    cats = [c for c, _ in tracks]
    assert "drum" not in cats                       # restricted 被剔除
    assert "bass" in cats and "guita" in cats       # free/pack 保留


@pytest.mark.smoke
def test_filter_release_safe_reports_dropped():
    files = ["a.wav", "b.wav"]
    entries = {"drum": {
        "a.wav": {"license_tier": "free"},
        "b.wav": {"license_tier": "restricted"},
    }}
    dropped: list = []
    kept = main._filter_release_safe(files, "drum", entries, dropped)
    assert kept == ["a.wav"]
    assert dropped == [("drum", 1)]


@pytest.mark.smoke
def test_make_unique_path_no_collision(tmp_path):
    from utils import make_unique_path

    p1 = make_unique_path(str(tmp_path), "phonk_remix", "", "wav")
    open(p1, "w").close()
    p2 = make_unique_path(str(tmp_path), "phonk_remix", "", "wav")
    assert p2 != p1
    assert not os.path.exists(p2)


def test_run_remix_integration(fake_root):
    """端到端：假素材库 3 轨混音，输出时长 = bars * 小节毫秒数。"""
    for cat, name in [("drum", "drum (1).wav"), ("bass", "bass (1).wav"),
                      ("guita", "guita (1).wav")]:
        write_wav(make_tone(6000, freq={"drum": 120, "bass": 60, "guita": 330}[cat]),
                  str(fake_root / cat / name))
    out_dir = str(fake_root / "out")
    path = main.run_remix(count=3, seed=7, out_dir=out_dir, fmt="wav",
                          bars=4, bpm=120)
    assert os.path.isfile(path)
    seg = AudioSegment.from_file(path)
    expected = main.bar_ms(120, 4)
    assert abs(len(seg) - expected) <= 200
