"""ingest_stems — 把整曲分离成 stem 并灌入 musickit 素材池（CC0 公版素材入库）。

背景（2026-11-02）：
  仓库的 `bass/ drum/ guita/ acapella/` 池要的是**分离后的 stem**，而公有领域音频站
  给的是整曲混音。本脚本把「整曲 → demucs 四轨 → 分池落盘 → 更新 manifest」串成一步。

映射（htdemucs 四轨）：
  drums.wav  → drum/      （鼓）
  bass.wav   → bass/      （贝斯）
  other.wav  → guita/     （旋律/其他；项目约定 other 轨即吉他/旋律轨）
  vocals.wav → acapella/  （人声）

用法：
  # A. 已分离（复用 demucs 产物目录 <out>/<model>/<track>/<stem>.wav）
  python remix/tools/ingest_stems.py --demucs-out D:/tmp/demucs_out

  # B. 从整曲一步到位（内部调 demucs 子进程）
  python remix/tools/ingest_stems.py --src D:/tmp/freepd_src --source-tag freepd

  # 只看计划不落盘
  python remix/tools/ingest_stems.py --demucs-out ... --dry-run

约定：
  - 目标文件名 `<source_tag>__<slug>.wav`，stem 类型由所在池隐含（不再进文件名）；
  - manifest 按 basename upsert，保留其它既有条目；
  - 音频本身被 .gitignore 排除（只提交 manifest.json），故本脚本产物不会进版本库；
  - 幂等：目标文件已存在且 sha256 相同则跳过。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REMIX_DIR not in sys.path:
    sys.path.insert(0, _REMIX_DIR)  # 本机 PYTHONSAFEPATH=1，脚本目录不自动入 sys.path

AUDIO_EXT = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aif")

#: demucs stem 名 → musickit 池
STEM_TO_POOL = {
    "drums": "drum",
    "bass": "bass",
    "other": "guita",
    "vocals": "acapella",
}

#: 分池的 subcategory（沿用池内既有命名风格）
POOL_SUBCATEGORY = {
    "drum": "full_stem",
    "bass": "full_stem",
    "guita": "full_stem",
    "acapella": "vocal_full",
}


def slugify(text: str) -> str:
    """把曲名压成安全的文件名片段（保留中文，其余转下划线）。"""
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", text, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s or "track")[:80]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_s(path: str) -> float:
    try:
        import soundfile as sf

        info = sf.info(path)
        if info.samplerate and info.frames:
            return round(info.frames / float(info.samplerate), 3)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _detect_indent(mpath: str) -> int:
    """沿用既有 manifest 的缩进，避免整库重排（历史上是 2 空格）。"""
    try:
        with open(mpath, encoding="utf-8") as f:
            for line in f:
                if line.startswith(" "):
                    return max(1, len(line) - len(line.lstrip(" ")))
                if line.strip() and not line.startswith("{"):
                    break
    except OSError:
        pass
    return 2


def load_manifest(pool_dir: str) -> dict:
    mpath = os.path.join(pool_dir, "manifest.json")
    if os.path.isfile(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("entries"), list):
                d["_indent"] = _detect_indent(mpath)
                return d
        except Exception:  # noqa: BLE001
            pass
    return {"generated_by": "ingest_stems.py", "entries": [], "_indent": 2}


def save_manifest(pool_dir: str, data: dict, dry_run: bool) -> None:
    """写回 manifest：保留原缩进与 LF 换行，保留原 generated_by 出处。"""
    if dry_run:
        return
    mpath = os.path.join(pool_dir, "manifest.json")
    tmp = mpath + ".tmp"
    indent = data.pop("_indent", 2)
    # 不覆盖原 generated_by（那是「谁生成过这个池」的出处），单独记本次灌库者
    data.setdefault("generated_by", "ingest_stems.py")
    data["last_ingested_by"] = "ingest_stems.py"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, mpath)


def upsert_entry(data: dict, entry: dict) -> str:
    """按 file 字段 upsert，返回 "insert" / "update"。"""
    for i, e in enumerate(data["entries"]):
        if isinstance(e, dict) and e.get("file") == entry["file"]:
            data["entries"][i] = {**e, **entry}
            return "update"
    data["entries"].append(entry)
    return "insert"


def pending_tracks(src_dir: str, root: str, source_tag: str) -> list[str]:
    """挑出尚未灌库的曲目（四池里都已有同名目标文件则视为已完成）。

    为什么需要：`--src` 模式每次都跑完整 demucs 分离（≈1.2× 实时）。对一个几十首的
    目录做增量补充时，重跑全部等于白烧几小时。这里按「目标文件是否已存在」做便宜判断
    （分离前无法算 sha256），配合 `--force` 可强制重做。
    """
    tracks = [f for f in sorted(os.listdir(src_dir)) if f.lower().endswith(AUDIO_EXT)]
    pending: list[str] = []
    for name in tracks:
        slug = slugify(os.path.splitext(name)[0])
        target = f"{source_tag}__{slug}.wav"
        if all(os.path.isfile(os.path.join(root, pool, target)) for pool in STEM_TO_POOL.values()):
            print(f"  [跳过] {name}（四池均已存在 {target}）")
            continue
        pending.append(name)
    return pending


def transcode_inputs(src_dir: str, work_dir: str, timeout: int = 900,
                     only: list[str] | None = None) -> list[str]:
    """把各种输入格式统一转成 44.1k/2ch/16bit WAV。

    为什么必须做：demucs 的音频加载器先走 sphn，对某些 mp3 流会报
    「malformed stream: mpa: invalid main_data offset」，而它自带的 ffmpeg
    回退在本机识别不到；先用系统 ffmpeg 归一化可同时解决格式兼容与采样率问题。
    """
    from core.binfind import require as _require_bin

    ffmpeg = _require_bin("ffmpeg")
    os.makedirs(work_dir, exist_ok=True)
    tracks = only if only is not None else [
        f for f in sorted(os.listdir(src_dir)) if f.lower().endswith(AUDIO_EXT)
    ]
    if not tracks:
        raise FileNotFoundError(f"{src_dir} 下没有待处理的音频文件")
    outs: list[str] = []
    for name in tracks:
        src = os.path.join(src_dir, name)
        stem = os.path.splitext(name)[0]
        dst = os.path.join(work_dir, f"{stem}.wav")
        cmd = [ffmpeg, "-y", "-v", "error", "-i", src,
               "-ac", "2", "-ar", "44100", "-sample_fmt", "s16", dst]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode != 0 or not os.path.isfile(dst):
            raise RuntimeError(f"转码失败（{name}）: {(r.stderr or '').strip()[-300:]}")
        outs.append(dst)
        print(f"  [转码] {name} → {os.path.basename(dst)}")
    return outs


def run_demucs(wav_inputs: list[str], out_dir: str, model: str, python: str,
               timeout: int) -> int:
    """对已归一化的 WAV 列表跑 demucs，返回退出码。"""
    cmd = [python, "-m", "demucs", "-n", model, "-o", out_dir, *wav_inputs]
    print(f"[demucs] {len(wav_inputs)} 首，模型 {model}（CPU 约 1.2× 实时，请耐心）")
    r = subprocess.run(cmd, timeout=timeout)
    return r.returncode


def collect_stems(demucs_out: str, model: str) -> list[tuple[str, str, str]]:
    """返回 [(stem_kind, track_name, wav_path), ...]。"""
    root = os.path.join(demucs_out, model)
    found: list[tuple[str, str, str]] = []
    if not os.path.isdir(root):
        # 也允许直接把某个 track 目录传进来
        root = demucs_out
    if not os.path.isdir(root):
        return found
    for entry in sorted(os.listdir(root)):
        tdir = os.path.join(root, entry)
        if not os.path.isdir(tdir):
            continue
        for kind in STEM_TO_POOL:
            p = os.path.join(tdir, f"{kind}.wav")
            if os.path.isfile(p):
                found.append((kind, entry, p))
    return found


def ingest(
    stems: list[tuple[str, str, str]],
    root: str,
    source_tag: str,
    license_text: str,
    license_tier: str,
    original_group: str,
    dry_run: bool,
) -> dict:
    stats = {"insert": 0, "update": 0, "skip_same": 0, "missing_pool": 0, "empty": 0}
    per_pool: dict[str, dict] = {}

    for kind, track, src in stems:
        pool = STEM_TO_POOL[kind]
        pool_dir = os.path.join(root, pool)
        if not os.path.isdir(pool_dir):
            print(f"⚠️ 池目录不存在，跳过：{pool_dir}", file=sys.stderr)
            stats["missing_pool"] += 1
            continue

        dur = duration_s(src)
        if dur <= 0:
            print(f"⚠️ 无法读取时长，跳过：{src}", file=sys.stderr)
            stats["empty"] += 1
            continue

        name = f"{source_tag}__{slugify(track)}.wav"
        dst = os.path.join(pool_dir, name)
        sha = sha256_file(src)

        same_on_disk = os.path.isfile(dst) and sha256_file(dst) == sha
        if same_on_disk:
            stats["skip_same"] += 1
        elif not dry_run:
            shutil.copy2(src, dst)
        # 注意：即使文件已存在也要继续走到 upsert —— 否则「manifest 被回滚/清空但
        # 音频还在」的场景下，条目永远补不回来（静默漏记）。

        data = per_pool.setdefault(pool, {"insert": 0, "update": 0, "skip": 0, "_manifest": None})
        if data["_manifest"] is None:
            data["_manifest"] = load_manifest(pool_dir)

        action = upsert_entry(data["_manifest"], {
            "file": name,
            "source_pack": source_tag,
            "original": f"{track}.mp3",
            "original_rel": f"{original_group}/{track}.mp3",
            "license": license_text,
            "license_tier": license_tier,
            "duration_s": dur,
            "sha256": sha,
            "subcategory": POOL_SUBCATEGORY.get(pool, "full_stem"),
            "content_kind": "stem",
        })
        stats[action] += 1
        data[action] += 1
        print(f"  {action:6s} {pool:<9} {name}  ({dur:.1f}s)")

    if not dry_run:
        for pool, d in per_pool.items():
            if d["_manifest"] is not None:
                save_manifest(os.path.join(root, pool), d["_manifest"], dry_run)
    return stats


def purge_by_tag(root: str, tag: str, dry_run: bool) -> dict:
    """删除 source_pack == tag 的 manifest 条目与对应音频文件。"""
    stats = {"entries": 0, "files": 0, "pools": 0}
    for pool in sorted(STEM_TO_POOL.values()):
        pool_dir = os.path.join(root, pool)
        if not os.path.isdir(pool_dir):
            continue
        data = load_manifest(pool_dir)
        keep, drop = [], []
        for e in data.get("entries", []):
            if isinstance(e, dict) and e.get("source_pack") == tag:
                drop.append(e)
            else:
                keep.append(e)
        if not drop:
            continue
        stats["pools"] += 1
        stats["entries"] += len(drop)
        data["entries"] = keep
        for e in drop:
            fpath = os.path.join(pool_dir, str(e.get("file", "")))
            if os.path.isfile(fpath):
                stats["files"] += 1
                print(f"  - 删除 {pool}/{os.path.basename(fpath)}")
                if not dry_run:
                    os.remove(fpath)
        save_manifest(pool_dir, data, dry_run)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="整曲分离 → 灌入 musickit stem 池")
    src_grp = ap.add_mutually_exclusive_group()
    src_grp.add_argument("--demucs-out", help="已有的 demucs 输出目录（跳过分离）")
    src_grp.add_argument("--src", help="整曲目录（内部调用 demucs 分离）")
    ap.add_argument("--purge-tag", metavar="TAG",
                    help="按 source_pack==TAG 删除条目与落盘文件（可逆性保障），"
                         "常配合 --dry-run 先看会删什么")
    ap.add_argument("--root", default=os.environ.get("MUSICKIT_ROOT")
                    or os.path.dirname(_REMIX_DIR),
                    help="musickit 根目录（池所在处，默认仓库根）")
    ap.add_argument("--model", default="htdemucs", help="demucs 模型名（默认 htdemucs）")
    ap.add_argument("--python", default=sys.executable, help="跑 demucs 的解释器")
    ap.add_argument("--source-tag", default="freepd", help="素材来源标签，用于文件前缀")
    ap.add_argument("--license", default="CC0 1.0 Public Domain (freepd.cn)",
                    help="license 文本，写入 manifest")
    ap.add_argument("--license-tier", default="free", help="license_tier（历史字段，仅记录）")
    ap.add_argument("--timeout", type=int, default=3600, help="demucs 超时秒数")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不落盘")
    ap.add_argument("--force", action="store_true",
                    help="忽略「四池已存在同名文件」，强制重新分离（默认跳过已完成）")
    args = ap.parse_args()

    if args.purge_tag:
        st = purge_by_tag(args.root, args.purge_tag, args.dry_run)
        print(f"\n清除 source_pack == '{args.purge_tag}'：池 {st['pools']} 个 / "
              f"条目 {st['entries']} 条 / 文件 {st['files']} 个"
              + ("（dry-run，未实际删除）" if args.dry_run else ""))
        return 0

    if not args.src and not args.demucs_out:
        print("❌ 需要 --src / --demucs-out / --purge-tag 之一", file=sys.stderr)
        return 2

    demucs_out = args.demucs_out
    if args.src:
        if args.force:
            todo = None
        else:
            todo = pending_tracks(args.src, args.root, args.source_tag)
            if not todo:
                print("✅ 该目录下所有曲目都已灌库，无需重做（--force 可强制重跑）")
                return 0
        work = tempfile.mkdtemp(prefix="stems_src_")
        print(f"[1/2] 归一化输入 → {work}")
        try:
            wavs = transcode_inputs(args.src, work, only=todo)
        except Exception as e:  # noqa: BLE001
            print(f"❌ 输入预处理失败: {e}", file=sys.stderr)
            return 2
        demucs_out = tempfile.mkdtemp(prefix="demucs_")
        print(f"[2/2] 分离 → {demucs_out}")
        rc = run_demucs(wavs, demucs_out, args.model, args.python, args.timeout)
        if rc != 0:
            print(f"❌ demucs 退出码 {rc}（已成功的曲目仍会被灌入）", file=sys.stderr)

    stems = collect_stems(demucs_out, args.model)
    if not stems:
        print(f"❌ 在 {demucs_out} 下没找到任何 {{drums,bass,other,vocals}}.wav", file=sys.stderr)
        return 2

    print(f"发现 {len(stems)} 个 stem，目标根目录 {args.root}"
          + ("（dry-run）" if args.dry_run else ""))
    stats = ingest(stems, args.root, args.source_tag, args.license,
                   args.license_tier, args.source_tag, args.dry_run)

    print("\n汇总：新增 {insert} / 更新 {update} / 跳过(内容相同) {skip_same} / "
          "缺池 {missing_pool} / 空文件 {empty}".format(**stats))
    if args.dry_run:
        print("（dry-run：未写入任何文件或 manifest）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
