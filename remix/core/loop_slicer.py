"""
loop_slicer — BPM 网格切片与 phonk beat 编排（纯业务逻辑，零 GUI 依赖）。

能力：
  - bar_ms(bpm, bars)：小节毫秒数
  - duration_ms(path)：ffprobe 探测时长（不整曲载入）
  - read_envelope(path, sr)：ffmpeg 解码为低采样率单声道包络（低内存扫描整曲）
  - best_loop_start(env, env_sr, loop_ms)：按能量峰值定位切片起点
  - load_slice(path, start_ms, dur_ms)：ffmpeg 只解码切片（内存优化 F4）
  - build_arrangement(tracks, bpm, total_bars)：把素材按角色铺成 total_bars 长度
  - audio_fingerprint(path)：时长 + 前 0.5s 内容哈希，跨格式判重（F6）
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import random
import re
import struct
import subprocess

import numpy as np
from pydub import AudioSegment

_BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
_FFMPEG = os.path.join(_BIN_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
_FFPROBE = os.path.join(_BIN_DIR, "ffprobe.exe" if os.name == "nt" else "ffprobe")

# 任何入口（CLI/GUI/测试）都能找到编解码器，无需系统安装 ffmpeg
if os.path.isdir(_BIN_DIR):
    os.environ["PATH"] = _BIN_DIR + os.pathsep + os.environ.get("PATH", "")
    if os.path.isfile(_FFMPEG):
        AudioSegment.converter = _FFMPEG
    if os.path.isfile(_FFPROBE):
        AudioSegment.ffprobe = _FFPROBE

# 角色 → 铺排方式
ROLE_LOOP = "loop"      # 循环填满
ROLE_ACCENT = "accent"  # 每 2 小节第 1 拍点缀（one-shot）
LONG_TRACK_MIN_BARS = 4  # 素材 >= 4 小节才切 loop，否则整段使用


def bar_ms(bpm: int, bars: int = 1) -> int:
    """1 小节的毫秒数（4/4 拍）。"""
    return int(round(60000.0 / bpm * 4 * bars))


def duration_ms(path: str) -> int:
    """ffprobe 探测时长（毫秒），失败返回 0。"""
    try:
        r = subprocess.run(
            [_FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60,
        )
        return int(round(float(json.loads(r.stdout)["format"]["duration"]) * 1000))
    except Exception:
        return 0


def read_envelope(path: str, sr: int = 8000) -> list[int]:
    """把音频解码为 sr 采样率单声道 s16 包络样本（用于低内存能量扫描）。"""
    r = subprocess.run(
        [_FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
         "-f", "s16le", "-"],
        capture_output=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 解码失败: {path}")
    n = len(r.stdout) // 2
    return list(struct.unpack("<%dh" % n, r.stdout))


def best_loop_start(
    env: list[int],
    env_sr: int,
    loop_ms: int,
    search_max_sec: float = 120.0,
    search_start_sec: float = 0.0,
) -> int:
    """在包络的 [search_start_sec, search_start_sec+search_max_sec) 区间里
    找能量最高的 loop_ms 窗口，返回起始毫秒（绝对时间，含区间偏移）。

    区间化搜索用于 A/B 变体：同一首歌不同段落各切一片。
    """
    win = max(1, int(loop_ms / 1000.0 * env_sr))
    begin = int(search_start_sec * env_sr)
    limit = min(len(env), begin + int(search_max_sec * env_sr))
    if limit - begin < win:
        return begin * 1000 // env_sr
    hop = max(1, win // 4)
    best_i, best_e = begin, -1.0
    for i in range(begin, limit - win + 1, hop):
        e = sum(x * x for x in env[i:i + win])
        if e > best_e:
            best_e, best_i = e, i
    return int(best_i / env_sr * 1000)


def load_slice(path: str, start_ms: int, dur_ms: int, tempo: float = 1.0) -> AudioSegment:
    """只解码 [start_ms, start_ms+dur_ms) 切片为 44.1kHz 立体声 16bit。

    tempo: atempo 变速系数（>1 加速，输出长度 = 输入/tempo）。
    """
    args = [_FFMPEG, "-v", "error", "-ss", f"{start_ms / 1000.0:.3f}",
            "-t", f"{dur_ms / 1000.0:.3f}", "-i", path]
    if tempo and abs(tempo - 1.0) > 1e-3:
        args += ["-af", f"atempo={tempo:.4f}"]
    args += ["-ar", "44100", "-ac", "2", "-f", "wav", "-"]
    r = subprocess.run(args, capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 切片失败: {path}")
    seg = AudioSegment.from_file(io.BytesIO(r.stdout), format="wav")
    return seg.set_frame_rate(44100).set_channels(2).set_sample_width(2)


def estimate_bpm(env: list[int], env_sr: int = 8000,
                 min_bpm: float = 70.0, max_bpm: float = 180.0) -> float | None:
    """自相关法估 BPM：10ms 能量窗口 → onset flux → 自相关峰 → 拍周期。

    返回 None 表示无法可靠估计（素材过短/无节奏结构）。
    """
    x = np.asarray(env, dtype=np.float64) / 32768.0
    win = max(1, int(env_sr * 0.01))
    n_win = len(x) // win
    if n_win < 400:  # 不足 4 秒
        return None
    xw = x[:n_win * win].reshape(n_win, win)
    energy = (xw ** 2).mean(axis=1)
    flux = np.clip(np.diff(energy), 0, None)
    flux = flux - flux.mean()
    if float(np.sum(flux ** 2)) < 1e-9:
        return None
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lag_min = max(1, int(60.0 / max_bpm / 0.01))   # 单位：10ms
    lag_max = min(len(ac) - 1, int(60.0 / min_bpm / 0.01))
    if lag_max <= lag_min:
        return None
    seg_ac = ac[lag_min:lag_max]
    lag = int(np.argmax(seg_ac)) + lag_min
    return 60.0 / (lag * 0.01)


def parse_bpm_hint(path: str) -> int | None:
    """从路径/文件名中提取 BPM 提示（如 ".../102bpm/..." 或 "..._102-..."）。"""
    m = re.search(r"(\d{2,3})\s*bpm", path, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"[_-](\d{2,3})[-_.]", os.path.basename(path))
    if m and 60 <= int(m.group(1)) <= 200:
        return int(m.group(1))
    return None


def build_arrangement(
    materials: list[dict],
    bpm: int,
    total_bars: int,
    fade_out_bars: int = 0,
) -> AudioSegment:
    """把各轨素材按角色铺成 total_bars 长度的成品。

    materials: [{"role": "loop"|"accent", "seg": AudioSegment, "gain_db": float,
                 "start_bar": int, "end_bar": int, "gain_curve": list[float]|None}, ...]
      start_bar/end_bar 控制该层在小节区间 [start, end) 内出现（段落编排）。
      gain_curve: 长度 = total_bars 的逐小节相对增益（dB），M4 段落强度曲线。
    fade_out_bars: 结尾整体淡出的小节数（0=不淡出）。
    """
    total_ms = bar_ms(bpm, total_bars)
    layered: list[AudioSegment] = []
    for m in materials:
        seg = m["seg"].set_frame_rate(44100).set_channels(2).set_sample_width(2)
        gain = m.get("gain_db", 0.0)
        if gain:
            seg = seg.apply_gain(gain)
        seg_b = m.get("seg_b")
        if seg_b is not None:
            seg_b = seg_b.set_frame_rate(44100).set_channels(2).set_sample_width(2)
            if gain:
                seg_b = seg_b.apply_gain(gain)
        role = m.get("role", ROLE_LOOP)
        start_bar = m.get("start_bar", 0)
        end_bar = m.get("end_bar", total_bars)
        start_ms = bar_ms(bpm, start_bar)
        end_ms = bar_ms(bpm, end_bar)
        curve = m.get("gain_curve")
        variant_every = m.get("variant_every_bars", 0) if seg_b is not None else 0
        if role == ROLE_ACCENT:
            base = AudioSegment.silent(duration=total_ms, frame_rate=44100).set_channels(2)
            bar = bar_ms(bpm)
            every = max(1, m.get("accent_every", 2))  # 每 N 小节点缀一次（默认 2）
            for i in range(start_bar, end_bar, every):
                piece = seg.apply_gain(curve[i]) if curve is not None and i < len(curve) else seg
                base = base.overlay(piece, position=min(i * bar, total_ms - 1))
            layered.append(base)
        else:
            # loop：按 variant_every_bars 分块，奇块用 B 变体（A-B 交替防单调），
            # 逐小节填充并施加 gain 曲线（材料尾部 8ms 微淡出，消除循环点爆音）
            base = AudioSegment.silent(duration=total_ms, frame_rate=44100).set_channels(2)
            bar = bar_ms(bpm)
            chunk_len = variant_every if variant_every else (end_bar - start_bar)
            cur = start_bar
            chunk_idx = 0
            while cur < end_bar:
                chunk_end = min(end_bar, cur + chunk_len)
                span_bars = chunk_end - cur
                src = (seg_b if (variant_every and chunk_idx % 2 == 1) else seg)
                src = src.fade_out(8)
                reps = (span_bars * bar) // len(src) + 2
                long_src = src * reps
                for b in range(cur, chunk_end):
                    off = (b - cur) * bar
                    piece = long_src[off:off + bar]
                    if curve is not None and b < len(curve) and curve[b]:
                        piece = piece.apply_gain(curve[b])
                    base = base.overlay(piece, position=b * bar)
                cur = chunk_end
                chunk_idx += 1
            layered.append(base)
    if not layered:
        return AudioSegment.silent(duration=total_ms, frame_rate=44100).set_channels(2)
    mix = layered[0]
    for t in layered[1:]:
        mix = mix.overlay(t)
    if fade_out_bars > 0:
        mix = mix.fade_out(bar_ms(bpm, fade_out_bars))
    return mix


def audio_fingerprint(path: str) -> str:
    """时长(0.1s 精度) + 前 0.5s 8kHz 单声道内容哈希，用于跨格式内容判重。"""
    dur = duration_ms(path) // 100  # 0.1s 粒度
    head = b""
    try:
        r = subprocess.run(
            [_FFMPEG, "-v", "error", "-t", "0.5", "-i", path,
             "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0:
            head = r.stdout
    except Exception:
        pass
    h = hashlib.sha256()
    h.update(str(dur).encode())
    h.update(head)
    return h.hexdigest()


def prepare_material(
    path: str,
    bpm: int,
    rng: random.Random,
    source_bpm: int | None = None,
    estimate_tempo: bool = True,
    search_start_sec: float = 0.0,
    search_max_sec: float = 120.0,
) -> AudioSegment:
    """按素材长短与源速决定用法（F1/F3-v2/F4/A-B 变体）：

    - 整曲（>= 4 小节）：能量定位 + 切 1~2 小节 loop；
      search_start_sec/search_max_sec 指定搜索区间（A/B 变体用不同段落）；
    - 短素材：整段载入（之后由 build_arrangement 决定循环或点缀）；
    - 源 BPM 已知（路径提示）或可估计时，atempo 拉伸到目标 BPM
      （比率钳制 0.85~1.18，避免时间拉伸伪影）。
    """
    dur = duration_ms(path)
    bar = bar_ms(bpm)
    # 确定源 BPM：显式提示 > 估计
    src_bpm = source_bpm or parse_bpm_hint(path)
    if src_bpm is None and estimate_tempo and dur >= 20000:
        try:
            src_bpm = estimate_bpm(read_envelope(path))
        except Exception:
            src_bpm = None
    ratio = 1.0
    if src_bpm and 60 <= src_bpm <= 200:
        ratio = min(max(bpm / src_bpm, 0.85), 1.18)
        if abs(ratio - 1.0) < 0.02:
            ratio = 1.0

    if dur >= bar * LONG_TRACK_MIN_BARS:
        loop_bars = rng.choice([1, 2])
        loop = bar * loop_bars
        env = read_envelope(path)
        start = best_loop_start(env, 8000, int(loop * ratio),
                                search_max_sec=search_max_sec,
                                search_start_sec=search_start_sec)
        return load_slice(path, start, int(loop * ratio), tempo=ratio)
    return load_slice(path, 0, max(dur, 300), tempo=ratio)
