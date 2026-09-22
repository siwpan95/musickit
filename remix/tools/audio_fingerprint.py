"""audio_fingerprint.py — 音频「内容指纹」工具（跨编码一致，用于复现核验）。

为什么需要它
------------
历史 mp3 会被改名/移动，索引里的路径不可靠；而 mp3 ↔ wav 的 sha256 天然不同。
所以用**包络指纹**：解码为 8 kHz 单声道 → 10 ms 窗 RMS 包络 → 按峰值归一后量化 → sha1。
同一编排在 128 kbps mp3 与 48 kHz/24 bit wav 上会得到相同的包络指纹（实测 r>0.998），
因此可以脱离文件名、脱离编码地判断「重渲产物是否就是原来那一首」。

用法
----
    from audio_fingerprint import envelope, envelope_corr, envelope_hash, sha256_file

注意：本机 `F:\\Python314` 设了 `PYTHONSAFEPATH=1`，脚本目录不会自动进 sys.path，
入口脚本需要 `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` 后再 import。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
FFMPEG = os.path.join(_BIN, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")

ENVELOPE_SR = 8000
WIN_MS = 10


def sha256_file(path: str) -> str | None:
    """整文件 sha256（仅用于「同编码同文件」的强一致校验）。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:  # noqa: BLE001
        return None


def envelope(path: str, sr: int = ENVELOPE_SR, win_ms: int = WIN_MS):
    """解码 → 单声道 → 10 ms 窗 RMS 包络（numpy array）；失败返回 None。"""
    import numpy as np

    win = max(1, sr * win_ms // 1000)
    try:
        r = subprocess.run(
            [FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
             "-f", "f32le", "-"],
            capture_output=True, timeout=300,
        )
    except Exception:  # noqa: BLE001
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    x = np.frombuffer(r.stdout, dtype="<f4")
    m = len(x) // win
    if m < 10:
        return None
    return np.sqrt((x[:m * win].reshape(m, win) ** 2).mean(axis=1) + 1e-12)


def envelope_corr(a_env, b_env) -> float | None:
    """两条包络的 Pearson 相关系数（1.0 = 内容一致）。"""
    import numpy as np

    if a_env is None or b_env is None:
        return None
    n = min(len(a_env), len(b_env))
    if n < 50:
        return None
    a, b = a_env[:n], b_env[:n]
    if a.std() < 1e-9 or b.std() < 1e-9:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def envelope_hash(path: str, levels: int = 256) -> str | None:
    """包络指纹：按峰值归一 → 量化 → sha1。跨编码稳定，内容变了就变。"""
    import numpy as np

    env = envelope(path)
    if env is None:
        return None
    peak = float(env.max())
    if peak <= 1e-12:
        return None
    q = np.clip(np.round(env / peak * (levels - 1)), 0, levels - 1).astype(np.uint8)
    return hashlib.sha1(q.tobytes()).hexdigest()


def fingerprint(path: str) -> dict:
    """一次性取全部指纹字段（写索引用）。"""
    return {
        "sha256": sha256_file(path),
        "envelope_hash": envelope_hash(path),
        "size_bytes": (os.path.getsize(path) if os.path.isfile(path) else None),
    }
