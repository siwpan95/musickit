"""Coollider Acapellas Vols.1-42 入库 → G:\\music\\musickit\\acapella\\

把已解压的 42 卷真人 acapella 按原始卷结构原样拷入新建的 acapella 池，
不做重编码（保持人声保真）。逐文件：
  - 流式拷贝并同时算 sha256（单次读取，避免二次全量读盘）
  - ffprobe 取时长（duration_s）
  - 登记 acapella/manifest.json（沿用项目统一 schema）
非音频文件（png/mid/flp 等）一并拷贝保留，但不写 manifest。

幂等：目标已存在且大小一致则跳过拷贝，仍补算 sha256/duration 并登记。
用法: python ingest_acapella.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 2026-09-23 去本地化：源包目录改由环境变量 ACAPELLA_SRC 指定（原百度网盘路径为本机专有）
_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])
SRC_ROOT = os.environ.get("ACAPELLA_SRC", "")
DEST = str(_MK_ROOT / "acapella")
FFPROBE = str(_MK_ROOT / "remix" / "bin" / "ffprobe.exe")
MANIFEST = os.path.join(DEST, "manifest.json")
SOURCE_PACK = "coollider_acapellas"
LICENSE = ("Coollider Acapellas Vols.1-42 (commercial sample pack; license unknown — "
           "do not redistribute the pack; internal/remix use at own risk)")
AUDIO_EXT = {".mp3", ".wav", ".flac", ".aiff", ".ogg", ".m4a", ".aac"}
CHUNK = 4 * 1024 * 1024


def probe_duration(path):
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30,
        )
        val = out.stdout.strip()
        if val and val != "N/A":
            return round(float(val), 2)
    except Exception:
        pass
    return None


def copy_with_hash(src, dst):
    h = hashlib.sha256()
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(CHUNK)
            if not chunk:
                break
            fo.write(chunk)
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated": None, "entries": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SRC_ROOT):
        print(f"[error] 源目录不存在: {SRC_ROOT}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(DEST, exist_ok=True)

    manifest = load_manifest(MANIFEST)
    existing = {e.get("file") for e in manifest.get("entries", [])}
    entries = manifest.get("entries", [])

    copied = skipped = failed = non_audio = 0
    for root, dirs, files in os.walk(SRC_ROOT):
        for name in sorted(files):
            src = os.path.join(root, name)
            rel = os.path.relpath(src, SRC_ROOT).replace(os.sep, "/")
            dst = os.path.join(DEST, rel)
            ext = os.path.splitext(name)[1].lower()
            if ext not in AUDIO_EXT:
                # 非音频：原样拷贝保留（不登记 manifest）
                if not args.dry_run and (not os.path.exists(dst) or
                                         os.path.getsize(dst) != os.path.getsize(src)):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(src, "rb") as fi, open(dst, "wb") as fo:
                        while True:
                            c = fi.read(CHUNK)
                            if not c:
                                break
                            fo.write(c)
                non_audio += 1
                continue

            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                skipped += 1
            else:
                if args.dry_run:
                    print(f"[dry-run] copy {rel}")
                else:
                    copy_with_hash(src, dst)
                    copied += 1

            if rel in existing:
                continue
            sha = None
            dur = None
            try:
                if not args.dry_run:
                    h = hashlib.sha256()
                    with open(dst, "rb") as f:
                        while True:
                            c = f.read(CHUNK)
                            if not c:
                                break
                            h.update(c)
                    sha = h.hexdigest()
                    dur = probe_duration(dst)
                entries.append({
                    "file": rel,
                    "source_pack": SOURCE_PACK,
                    "original": name,
                    "original_rel": rel,
                    "license": LICENSE,
                    "duration_s": dur,
                    "sha256": sha,
                })
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"[fail] {rel}: {e}", file=sys.stderr)

    manifest["generated"] = datetime.now().isoformat(timespec="seconds")
    manifest["entries"] = entries
    print(f"拷贝 {copied}（跳过已存在 {skipped}） | 非音频 {non_audio} | "
          f"失败 {failed} | manifest 条目 {len(entries)}")
    if not args.dry_run:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"manifest 已写入 {MANIFEST}")


if __name__ == "__main__":
    main()
