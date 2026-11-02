"""Mixkit 音效入库：动物叫声 → animal/、riser/impact/transition → sfx/。

归一化（44.1k 立体声 16bit、修剪静音、峰值 -3dBFS、sha256 去重）后编号入库，
manifest 记录来源与授权（Mixkit License：个人/商用免费，勿转售音效本体）。
用法: python ingest_mixkit.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

import subprocess
import tempfile
from pathlib import Path

# 2026-09-23 去本地化（仓根）；2026-11-02 修正：必须先定义再被 _BIN 引用（原顺序导致 NameError）
_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])

_REMIX_DIR = str(_MK_ROOT / "remix")
if _REMIX_DIR not in sys.path:
    sys.path.insert(0, _REMIX_DIR)

_BIN = str(_MK_ROOT / "remix" / "bin")
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
from pydub import AudioSegment  # noqa: E402
from pydub.silence import detect_leading_silence  # noqa: E402

DOWNLOADS = str(_MK_ROOT / "archived" / "downloads")
TARGETS = {
    "mixkit_animals": {"dir": str(_MK_ROOT / "animal"), "prefix": "animal"},
    "mixkit_sfx": {"dir": str(_MK_ROOT / "sfx"), "prefix": "sfx"},
}
LICENSE = "Mixkit License (personal/commercial free; do not redistribute the SFX as-is)"
SILENCE_THRESH = -45.0
TARGET_PEAK = -3.0
MAX_MS = 16000
MIN_MS = 100


def _to_wav(src: str, tmpdir: str) -> str:
    """先用 ffmpeg 转成 44.1k/2ch/16bit WAV，再交给 pydub。

    为什么必须做：pydub 读 mp3 时会调 ffprobe 取媒体信息，而本机没有 ffprobe
    （`remix/bin/` 从未入库），于是 178 个里 14 个直接 `[WinError 2]` 失败。
    用 ffmpeg 先归一化可完全绕开 prober。
    """
    from core.binfind import require as _require_bin

    ffmpeg = _require_bin("ffmpeg")
    dst = os.path.join(tmpdir, "in.wav")
    r = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", src,
         "-ac", "2", "-ar", "44100", "-sample_fmt", "s16", dst],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError(f"转码失败: {(r.stderr or '').strip()[-200:]}")
    return dst


def load_manifest(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def max_number(cat_dir, prefix):
    best = 0
    if os.path.isdir(cat_dir):
        for name in os.listdir(cat_dir):
            m = re.search(re.escape(prefix) + r" \((\d+)\)\.wav", name)
            if m:
                best = max(best, int(m.group(1)))
    return best


def _detect_indent(path: str) -> int:
    """沿用既有 manifest 的缩进，避免整库重排。"""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(" "):
                    return max(1, len(line) - len(line.lstrip(" ")))
    except OSError:
        pass
    return 2


def _write_manifest(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    indent = _detect_indent(path)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for sub, cfg in TARGETS.items():
        src_dir = os.path.join(DOWNLOADS, sub)
        if not os.path.isdir(src_dir):
            print(f"[skip] {src_dir} 不存在")
            continue
        os.makedirs(cfg["dir"], exist_ok=True)
        manifest = load_manifest(os.path.join(cfg["dir"], "manifest.json"))
        seen = set(e.get("sha256") for e in manifest["entries"])
        num = max_number(cfg["dir"], cfg["prefix"]) + 1
        ok = dup = fail = 0
        for name in sorted(os.listdir(src_dir)):
            if not name.lower().endswith((".wav", ".mp3")):
                continue
            try:
                with tempfile.TemporaryDirectory(prefix="mixkit_") as _td:
                    _wav = _to_wav(os.path.join(src_dir, name), _td)
                    seg = AudioSegment.from_file(_wav)
                seg = seg.set_channels(2).set_frame_rate(44100).set_sample_width(2)
                if not (MIN_MS <= len(seg) <= MAX_MS):
                    continue
                lead = detect_leading_silence(seg, silence_threshold=SILENCE_THRESH, chunk_size=10)
                seg = seg[lead:]
                rev = seg.reverse()
                trail = detect_leading_silence(rev, silence_threshold=SILENCE_THRESH, chunk_size=10)
                seg = seg[:len(seg) - trail]
                if len(seg) < MIN_MS or seg.dBFS < SILENCE_THRESH:
                    continue
                seg = seg.apply_gain(TARGET_PEAK - seg.max_dBFS)
                h = hashlib.sha256(seg.raw_data).hexdigest()
                if h in seen:
                    dup += 1
                    continue
                seen.add(h)
                out_name = f"{cfg['prefix']} ({num}).wav"
                if not args.dry_run:
                    seg.export(os.path.join(cfg["dir"], out_name), format="wav")
                manifest["entries"].append({
                    "file": out_name,
                    "source_pack": sub,
                    "original": name,
                    "original_rel": f"{sub}/{name}",
                    "license": LICENSE,
                    "license_tier": "free",
                    "duration_s": round(seg.duration_seconds, 2),
                    "sha256": h,
                })
                num += 1
                ok += 1
            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"[fail] {name}: {e}", file=sys.stderr)
        manifest["generated"] = datetime.now().isoformat(timespec="seconds")
        print(f"[{cfg['prefix']}] 入库 {ok}（去重 {dup}、失败 {fail}）→ {cfg['dir']} "
              f"manifest 共 {len(manifest['entries'])} 条")
        if not args.dry_run:
            _write_manifest(os.path.join(cfg["dir"], "manifest.json"), manifest)


if __name__ == "__main__":
    main()
