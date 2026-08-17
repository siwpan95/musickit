"""loop_slicer 单元测试 — 合成音频驱动，不依赖真实素材库。"""
import io
import os
import random
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import loop_slicer  # noqa: E402
from pydub import AudioSegment  # noqa: E402


def make_tone(ms: int, freq: int = 440) -> AudioSegment:
    """生成正弦波测试音频（不依赖 pydub.generators，兼容所有 pydub 版本）。"""
    import array
    import math
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


def test_bar_ms():
    assert loop_slicer.bar_ms(60, 1) == 4000   # 60BPM 1 小节 = 4s
    assert loop_slicer.bar_ms(120, 2) == 4000  # 120BPM 2 小节 = 4s
    assert loop_slicer.bar_ms(140, 16) == int(round(60000 / 140 * 4 * 16))


def test_duration_ms(tmp_path):
    p = write_wav(make_tone(1500), os.path.join(tmp_path, "t.wav"))
    assert abs(loop_slicer.duration_ms(p) - 1500) <= 50


def test_load_slice(tmp_path):
    p = write_wav(make_tone(4000), os.path.join(tmp_path, "t.wav"))
    seg = loop_slicer.load_slice(p, 1000, 1000)
    assert 900 <= len(seg) <= 1100
    assert seg.frame_rate == 44100 and seg.channels == 2 and seg.sample_width == 2


def test_read_envelope_and_best_start(tmp_path):
    # 前 2s 静音、中段 2s 响、后 2s 静音 → 能量峰应落在中段
    quiet = make_tone(2000).apply_gain(-60)
    loud = make_tone(2000)
    seg = quiet + loud + quiet
    p = write_wav(seg, os.path.join(tmp_path, "env.wav"))
    env = loop_slicer.read_envelope(p)
    start = loop_slicer.best_loop_start(env, 8000, loop_ms=1000, search_max_sec=10)
    assert 1500 <= start <= 3500  # 落在中段附近


def test_build_arrangement_loop_fill():
    bpm = 120
    bars = 8
    total = loop_slicer.bar_ms(bpm, bars)
    seg = make_tone(loop_slicer.bar_ms(bpm, 2))
    out = loop_slicer.build_arrangement([{"role": loop_slicer.ROLE_LOOP, "seg": seg}], bpm, bars)
    assert abs(len(out) - total) <= 50


def test_build_arrangement_accent_placement():
    bpm = 120
    bars = 8
    seg = make_tone(300)
    out = loop_slicer.build_arrangement([{"role": loop_slicer.ROLE_ACCENT, "seg": seg}], bpm, bars)
    assert abs(len(out) - loop_slicer.bar_ms(bpm, bars)) <= 50
    # 能量应集中在偶数小节开头（每 2 小节一次，共 4 次）
    # 注意：get_array_of_samples() 为交错采样，窗口需乘声道数
    arr = out.get_array_of_samples()
    bar_samples = loop_slicer.bar_ms(bpm) * 44100 * out.channels // 1000
    rms_at = []
    for i in range(bars):
        win = arr[i * bar_samples:(i + 1) * bar_samples]
        if win:
            rms_at.append(sum(x * x for x in win))
    # 偶数小节（0,2,4,6）应有明显能量，奇数小节近零
    for i in (0, 2, 4, 6):
        assert rms_at[i] > 0
    for i in (1, 3, 5, 7):
        assert rms_at[i] < rms_at[0] * 0.05


def test_audio_fingerprint_stable_and_content_based(tmp_path):
    p1 = write_wav(make_tone(1000, 440), os.path.join(tmp_path, "a.wav"))
    p2 = write_wav(make_tone(1000, 880), os.path.join(tmp_path, "b.wav"))
    assert loop_slicer.audio_fingerprint(p1) == loop_slicer.audio_fingerprint(p1)
    assert loop_slicer.audio_fingerprint(p1) != loop_slicer.audio_fingerprint(p2)


def test_prepare_material_long_track_slices_loop(tmp_path):
    # 12 小节长素材 → 应切出 1~2 小节 loop
    seg = make_tone(12000)
    p = write_wav(seg, os.path.join(tmp_path, "long.wav"))
    rng = random.Random(1)
    loop = loop_slicer.prepare_material(p, 120, rng)
    one_bar = loop_slicer.bar_ms(120)
    assert one_bar * 1 <= len(loop) <= one_bar * 2 + 200


def _click_track_ms(ms, bpm):
    """生成 BPM 节拍 click 音频（每拍 20ms 短脉冲）。"""
    import array
    import math
    sr = 44100
    n = int(sr * ms / 1000)
    buf = array.array("h", [0] * n)
    beat = int(sr * 60 / bpm)
    for start in range(0, n, beat):
        for i in range(start, min(start + int(sr * 0.02), n)):
            buf[i] = 25000
    return AudioSegment(buf.tobytes(), frame_rate=sr, sample_width=2, channels=1)


def test_estimate_bpm_click_track(tmp_path):
    seg = _click_track_ms(30000, 120)
    p = write_wav(seg, os.path.join(tmp_path, "click120.wav"))
    env = loop_slicer.read_envelope(p)
    est = loop_slicer.estimate_bpm(env)
    assert est is not None
    assert abs(est - 120) <= 3


def test_load_slice_tempo_stretch(tmp_path):
    seg = make_tone(2000, 440)
    p = write_wav(seg, os.path.join(tmp_path, "t.wav"))
    slow = loop_slicer.load_slice(p, 0, 2000, tempo=0.5)
    assert 3800 <= len(slow) <= 4200  # 0.5 倍速 → 时长翻倍
    fast = loop_slicer.load_slice(p, 0, 2000, tempo=2.0)
    assert 900 <= len(fast) <= 1100  # 2 倍速 → 时长减半


def test_parse_bpm_hint():
    assert loop_slicer.parse_bpm_hint(r"G:\x\EBM\102bpm\EBM_Beat_102-01.wav") == 102
    assert loop_slicer.parse_bpm_hint(r"G:\x\DH_BeatA-124-01.wav") == 124
    assert loop_slicer.parse_bpm_hint(r"G:\x\synth (51).wav") is None


def test_build_arrangement_sections_and_fade():
    bpm = 120
    bars = 32
    total = loop_slicer.bar_ms(bpm, bars)
    seg = make_tone(loop_slicer.bar_ms(bpm, 2))
    # bass 层只出现在 4~28 小节
    out = loop_slicer.build_arrangement(
        [{"role": loop_slicer.ROLE_LOOP, "seg": seg,
          "start_bar": 4, "end_bar": bars - 4}],
        bpm, bars, fade_out_bars=2,
    )
    assert abs(len(out) - total) <= 50
    arr = out.get_array_of_samples()
    ch = out.channels
    bar_samples = loop_slicer.bar_ms(bpm) * 44100 * ch // 1000
    rms = []
    for i in range(bars):
        win = arr[i * bar_samples:(i + 1) * bar_samples]
        rms.append(sum(x * x for x in win))
    assert rms[1] == 0                     # intro 段（4 小节前）无 bass
    assert rms[8] > 0                      # 中段有 bass
    assert rms[bars - 1] < rms[8] * 0.3    # 结尾淡出


def test_build_arrangement_ab_variant():
    """A/B 变体：每 4 小节切换素材，奇块内容应与偶块不同。"""
    bpm = 120
    bars = 16
    a = make_tone(loop_slicer.bar_ms(bpm, 1), freq=440)
    b = make_tone(loop_slicer.bar_ms(bpm, 1), freq=880)
    out = loop_slicer.build_arrangement(
        [{"role": loop_slicer.ROLE_LOOP, "seg": a, "seg_b": b,
          "variant_every_bars": 4}],
        bpm, bars,
    )
    assert abs(len(out) - loop_slicer.bar_ms(bpm, bars)) <= 50
    arr = out.get_array_of_samples()
    ch = out.channels
    bar_samples = loop_slicer.bar_ms(bpm) * 44100 * ch // 1000
    chunks = []
    for i in range(0, bars, 4):
        win = arr[i * bar_samples:(i + 4) * bar_samples]
        chunks.append(bytes(win))
    assert chunks[0] == chunks[2]          # A 每两个块回归
    assert chunks[1] == chunks[3]          # B 同样
    assert chunks[0] != chunks[1]          # A 与 B 内容不同（440Hz vs 880Hz）


def test_prepare_material_ab_regions(tmp_path):
    """同曲不同搜索区间应切出不同位置的 loop。"""
    import array
    import math
    # 前 10s 静音 → 10s 处 440Hz 响 → 30s 处 880Hz 响
    sr = 44100
    quiet = make_tone(10000).apply_gain(-60)
    a_seg = make_tone(2000, 440)
    quiet2 = make_tone(20000).apply_gain(-60)
    b_seg = make_tone(2000, 880)
    seg = quiet + a_seg + quiet2 + b_seg
    p = write_wav(seg, os.path.join(tmp_path, "ab.wav"))
    rng = random.Random(1)
    mat_a = loop_slicer.prepare_material(p, 120, rng, estimate_tempo=False,
                                         search_start_sec=0.0, search_max_sec=15.0)
    rng2 = random.Random(1)
    mat_b = loop_slicer.prepare_material(p, 120, rng2, estimate_tempo=False,
                                         search_start_sec=25.0, search_max_sec=15.0)
    # 两者首样本差异显著（不同频率段）
    aa = mat_a.get_array_of_samples()[:200]
    bb = mat_b.get_array_of_samples()[:200]
    diff = sum(abs(x - y) for x, y in zip(aa, bb))
    assert diff > 100000
