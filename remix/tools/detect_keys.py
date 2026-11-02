"""detect_keys — 用 librosa 的 chroma 估计每个素材的调性，写回 manifest（T2-1 前置）。

为什么需要：想让提示词里的 `scale` 真正影响选音，素材首先得知道自己是什么调。
manifest 目前没有 `key` 字段，人工标注 3 万条不现实，故用音频反推。

算法（Krumhansl-Schmuckler 简化版）：
  1. 取曲目中段 30s（避开前奏静音/淡入）
  2. librosa 求 chroma_cqt，按时间平均得到 12 维音级分布
  3. 与 24 个调性模板（12 音级 × 大小调）做 Pearson 相关，取最大者为估计调
  4. 置信度 = 最佳相关值；同时记录次佳用于判断区分度

只处理**有音高的池**（bass / guita / keys / strings / brass / woodwind / ethnic /
synth / acapella）。drum / cowbell / animal / sfx 是打击/音效，无调性，跳过。

用法：
  python remix/tools/detect_keys.py                  # 只补缺 key 的
  python remix/tools/detect_keys.py --force          # 全部重算
  python remix/tools/detect_keys.py --pools bass guita --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REMIX_DIR not in sys.path:
    sys.path.insert(0, _REMIX_DIR)
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from core.musical_key import NAMES, format_short  # noqa: E402

#: 有音高的池（打击/音效无调性，不检测）
PITCHED_POOLS = ("bass", "guita", "keys", "strings", "brass",
                 "woodwind", "ethnic", "synth", "acapella")

AUDIO_EXT = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aif")

# Krumhansl-Schmuckler 调性轮廓
PROF_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
PROF_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def estimate_key(path: str, excerpt_s: float = 30.0) -> tuple[int, str, float, float] | None:
    """返回 (音级, 'major'|'minor', 置信度, 次佳差值)；失败返回 None。"""
    import numpy as np
    import librosa
    import soundfile as sf

    try:
        info = sf.info(path)
        total = info.frames / float(info.samplerate) if info.samplerate else 0.0
    except Exception:  # noqa: BLE001
        return None
    if total <= 0:
        return None
    offset = max(0.0, total / 2 - excerpt_s / 2)
    try:
        y, sr = librosa.load(path, sr=22050, mono=True, offset=offset,
                             duration=min(excerpt_s, total))
    except Exception:  # noqa: BLE001
        return None
    if y.size == 0:
        return None

    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    except Exception:  # noqa: BLE001
        return None
    if not np.any(chroma):
        return None
    return _score_chroma(chroma)


def _slug_of(fname: str) -> str:
    """freepd__Alls_Fair_In_Love.wav → Alls_Fair_In_Love（去掉来源前缀）。"""
    base = os.path.splitext(fname)[0]
    return base.split("__", 1)[1] if "__" in base else base


def estimate_key_from_files(paths: list[str], excerpt_s: float = 30.0):
    """把多轨相加后估计调性（同一首曲子的各个 stem 共享一个调）。

    为什么必须相加：单独看某一路 stem 会偏 —— 贝斯只剩根音、人声只剩旋律，
    实测同一首曲子的 bass/guita/acapella 会被判成三个不同调（且 margin 低到 0.02）。
    相加后保留完整和声，估计稳定得多。
    """
    import numpy as np
    import librosa
    import soundfile as sf

    ys = []
    sr_out = 22050
    offset = 0.0
    for i, path in enumerate(paths):
        try:
            info = sf.info(path)
            total = info.frames / float(info.samplerate) if info.samplerate else 0.0
            if total <= 0:
                continue
            if i == 0:
                offset = max(0.0, total / 2 - excerpt_s / 2)
            y, _ = librosa.load(path, sr=sr_out, mono=True, offset=offset,
                                duration=min(excerpt_s, total))
            if y.size:
                ys.append(y)
        except Exception:  # noqa: BLE001
            continue
    if not ys:
        return None
    n = min(len(y) for y in ys)
    y = np.sum([v[:n] for v in ys], axis=0)
    if not np.any(y):
        return None
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr_out).mean(axis=1)
    except Exception:  # noqa: BLE001
        return None
    if not np.any(chroma):
        return None
    return _score_chroma(chroma)


def _score_chroma(chroma):
    import numpy as np

    c = chroma - chroma.mean()
    cnorm = float(np.linalg.norm(c)) or 1e-9
    best = (-2.0, 0, "major")
    scores: list[float] = []
    for pc in range(12):
        for mode, prof in (("major", PROF_MAJOR), ("minor", PROF_MINOR)):
            p = np.roll(np.asarray(prof, dtype=float), pc)
            p = p - p.mean()
            r = float(np.dot(c, p) / (cnorm * (float(np.linalg.norm(p)) or 1e-9)))
            scores.append(r)
            if r > best[0]:
                best = (r, pc, mode)
    scores.sort(reverse=True)
    margin = scores[0] - scores[1] if len(scores) > 1 else 0.0
    return best[1], best[2], round(best[0], 4), round(margin, 4)


def _load(pool_dir: str) -> dict:
    p = os.path.join(pool_dir, "manifest.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("entries"), list):
            return d
    return {"generated_by": "detect_keys.py", "entries": []}


def _indent(pool_dir: str) -> int:
    p = os.path.join(pool_dir, "manifest.json")
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.startswith(" "):
                    return max(1, len(line) - len(line.lstrip(" ")))
    except OSError:
        pass
    return 2


def _save(pool_dir: str, data: dict) -> None:
    p = os.path.join(pool_dir, "manifest.json")
    tmp = p + ".tmp"
    indent = _indent(pool_dir)
    data.setdefault("generated_by", "detect_keys.py")
    data["last_key_scan_by"] = "detect_keys.py"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser(description="估计素材调性并写回 manifest")
    ap.add_argument("--root", default=os.environ.get("MUSICKIT_ROOT")
                    or os.path.dirname(_REMIX_DIR))
    ap.add_argument("--pools", nargs="*", default=list(PITCHED_POOLS))
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 首曲目（0=全部）")
    ap.add_argument("--force", action="store_true", help="已有 key 也重算")
    ap.add_argument("--no-group", action="store_true",
                    help="按文件单独检测（默认按曲目聚合：同一首曲子的各 stem 共享一个调）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写 manifest")
    args = ap.parse_args()

    # 收集：slug -> [(pool, pool_dir, entry, path), ...]
    groups: dict[str, list[tuple[str, str, dict, str]]] = {}
    manifests: dict[str, dict] = {}
    for pool in args.pools:
        pool_dir = os.path.join(args.root, pool)
        if not os.path.isdir(pool_dir):
            continue
        data = _load(pool_dir)
        manifests[pool] = data
        on_disk = {n for n in os.listdir(pool_dir) if n.lower().endswith(AUDIO_EXT)}
        for e in data.get("entries", []):
            if not isinstance(e, dict) or e.get("file") not in on_disk:
                continue
            key = e["file"] if args.no_group else _slug_of(e["file"])
            groups.setdefault(key, []).append(
                (pool, pool_dir, e, os.path.join(pool_dir, e["file"]))
            )

    done = skip = fail = 0
    items = sorted(groups.items())
    if args.limit:
        items = items[: args.limit]
    print(f"待处理曲目 {len(items)} 组（--no-group 时即文件数）")

    for slug, members in items:
        if not args.force and all(m[2].get("key") for m in members):
            skip += len(members)
            continue
        paths = [m[3] for m in members]
        res = (estimate_key(paths[0]) if args.no_group else estimate_key_from_files(paths))
        if not res:
            print(f"  ⚠️  分析失败：{slug}")
            fail += 1
            continue
        pc, mode, conf, margin = res
        pools_txt = "/".join(sorted({m[0] for m in members}))
        print(f"  ✅ {slug[:40]:40s} → {format_short(pc, mode):4s} "
              f"(conf {conf:+.3f}, margin {margin:.3f})  [{pools_txt}]")
        for _pool, _pdir, e, _path in members:
            e["key"] = NAMES[pc]
            e["scale"] = mode
            e["key_confidence"] = conf
            e["key_margin"] = margin
            e["key_source"] = "per_file" if args.no_group else "track_mix"
            done += 1

    if not args.dry_run:
        for pool in {m[0] for members in groups.values() for m in members}:
            if pool in manifests:
                _save(os.path.join(args.root, pool), manifests[pool])

    print(f"\n完成：写入 {done} 条 / 跳过(已有) {skip} 条 / 失败 {fail} 组"
          + ("（dry-run，未写 manifest）" if args.dry_run else ""))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
