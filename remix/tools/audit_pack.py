"""Phase 2 步骤 2：审计下载的采样包。
扫描 archived/downloads 下解包出的目录，用内置 ffprobe 检测每个音频：
  - 目录关键词白名单：synth/lead/key/chord/pad/stab/bass/organ/piano/ep
  - 目录关键词黑名单：drum/kick/snare/hat/tom/cym/perc/fx/sfx/vocal/fill/loop_drum 等
  - 时长 0.3 ~ 8.0 s、采样率 >= 44100
  - 平均音量 > -45 dB（排除静音文件）
输出 candidates.json 供 ingest_synth.py 使用。
用法: python audit_pack.py
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）
DOWNLOADS = str(_MK_ROOT / "archived" / "downloads")
FFPROBE = str(_MK_ROOT / "remix" / "bin" / "ffprobe.exe")
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff", ".aif")
INCLUDE = re.compile(r"(synth|syn\b|lead|key|chord|pad|stab|bass|organ|piano|pluck|arp|melody|wave|glass|operator|guitar|gtr|riff|chug|wah|fuzz)", re.I)
EXCLUDE = re.compile(r"(beat|drum|kick|snare|hat|tom|cym|perc|fx|sfx|vocal|voice|shaker|clap|fill|riser|impact|noise|foley)", re.I)
MAX_DUR = 8.0
MIN_DUR = 0.3


def probe(path):
    """返回 (duration, sample_rate) 或 None。"""
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration,sample_rate",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        st = data["streams"][0]
        dur = float(st.get("duration") or 0)
        if dur <= 0:
            r2 = subprocess.run(
                [FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=30,
            )
            try:
                dur = float(json.loads(r2.stdout)["format"]["duration"])
            except Exception:
                dur = 0.0
        sr = int(st.get("sample_rate") or 0)
        return dur, sr
    except Exception:
        return None


def mean_volume(path):
    """用 volumedetect 取平均音量（dB），失败返回 -100。"""
    try:
        r = subprocess.run(
            [FFPROBE.replace("ffprobe.exe", "ffmpeg.exe"), "-hide_banner", "-i", path,
             "-af", "volumedetect", "-f", "null", "NUL"],
            capture_output=True, text=True, timeout=60,
        )
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr or r.stdout)
        return float(m.group(1)) if m else -100.0
    except Exception:
        return -100.0


def walk_audio(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        for fn in sorted(filenames):
            if fn.lower().endswith(AUDIO_EXT):
                yield os.path.join(dirpath, fn), rel, fn


def main():
    candidates = []
    scanned = 0
    skipped_dir = 0
    skipped_dur = 0
    skipped_silent = 0
    failed = 0
    for fp, rel, fn in walk_audio(DOWNLOADS):
        # 跳过 zip 自身与页面文件
        if rel.startswith(".") or fp.lower().endswith(".zip"):
            continue
        scanned += 1
        # 目录与文件名都要过关键词（EBM 包按 bpm 分目录，关键词在文件名）
        haystack = rel + "/" + fn
        if not INCLUDE.search(haystack) or EXCLUDE.search(haystack):
            skipped_dir += 1
            continue
        info = probe(fp)
        if info is None:
            failed += 1
            continue
        dur, sr = info
        if not (MIN_DUR <= dur <= MAX_DUR):
            skipped_dur += 1
            continue
        if sr < 44100:
            skipped_dur += 1
            continue
        mv = mean_volume(fp)
        if mv < -45.0:
            skipped_silent += 1
            continue
        candidates.append({
            "path": fp, "rel": rel, "name": fn,
            "duration": round(dur, 2), "sample_rate": sr, "mean_db": round(mv, 1),
        })
    print(f"扫描 {scanned} 个音频；目录过滤 {skipped_dir}；时长/采样率过滤 {skipped_dur}；"
          f"静音过滤 {skipped_silent}；探测失败 {failed}；候选 {len(candidates)}")
    # 按路径稳定排序
    candidates.sort(key=lambda c: c["rel"] + "/" + c["name"])
    out = os.path.join(DOWNLOADS, "candidates.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now().isoformat(timespec="seconds"),
                   "candidates": candidates}, f, ensure_ascii=False, indent=1)
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
