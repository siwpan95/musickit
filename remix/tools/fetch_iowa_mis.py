#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_iowa_mis —— 从爱荷华大学乐器采样库（MIS）抓单音素材，填 keys/strings/brass/woodwind 四池。

## 为什么用这个源

四个"乐器池"一直是 0 文件：manifest 里躺着上万个条目，但那是**商业采样包**的索引，
音频本体从来没进过仓库（`.gitignore` 排除音频），等于选音时无米下锅。
找 CC0 采样的路被墙了一大半（GitHub / jsDelivr / archive.org 全不通），
MIS 是实测能下、且唯一覆盖四个池的源：

- 站点原话："Since 1997, these recordings have been freely available on this website
  and may be downloaded and used for any projects, **without restrictions**."
- 内容形态：**单音 one-shot**（每个音一条），不用拆 SoundFont，正好是混音引擎要的东西。
- 实测：`Range: bytes=0-1023` 稳定 206（2/2 轮），不是"首页能打开"。

## 它在做什么

1. 抓乐器页（`MISviolin.html` 这类）里的 `sound files/**.aiff` 链接
2. 下载到缓存目录（可重试、已存在跳过）
3. 用 ffmpeg 转成 44.1kHz/16bit WAV（项目统一规格；单声道保持单声道——
   `audio_loader` 会按目标声道数 `set_channels` 统一，不必强行上立体声）
4. 平铺进对应池（本仓池子的约定：文件在池根，靠 manifest 的 `subcategory` 分类）
5. 写回 manifest：来源 / 原始文件名 / 授权原文 / 时长 / sha256

## 关于 `key`

**故意不写。** 除钢琴外，MIS 的文件名是音域范围（`Violin.arco.pp.sulG.G3B3.aiff`
意思是这条样本覆盖 G3~B3），根音并不明确 —— 按范围起点猜音级会污染 `--key` 的选音。
需要调性就抓完再跑 `detect_keys.py`，让它用 chroma 实测（单音样本测得准）。

## 用法

    # 先看计划（不下载）
    python remix/tools/fetch_iowa_mis.py --limit 2 --dry-run

    # 四池各下 12 条
    python remix/tools/fetch_iowa_mis.py --instruments piano violin trumpet flute --limit 12

    # 只补某一个池
    python remix/tools/fetch_iowa_mis.py --instruments cello oboe --limit 8
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
import time
import urllib.parse
import urllib.request

_REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REMIX_DIR not in sys.path:
    sys.path.insert(0, _REMIX_DIR)

from core import binfind  # noqa: E402

BASE = "https://theremin.music.uiowa.edu"
UA = "Mozilla/5.0 (compatible; musickit-fetch/1.0)"
LICENSE_TEXT = ("University of Iowa Musical Instrument Samples (MIS) — 站点声明"
                "「may be downloaded and used for any projects, without restrictions」"
                "（自 1997 年起公开，无 NC、无强制署名）")
SOURCE_PACK = "University of Iowa MIS"

# 乐器页 -> (池, subcategory, 链接前缀里的目录名)
# subcategory 取值沿用各池 manifest 里已有的词，避免出现"两套说法"。
PAGES: dict[str, tuple[str, str, str]] = {
    # 弦乐
    "violin":       ("strings", "violin", "Strings/violin"),
    "viola":        ("strings", "viola", "Strings/viola"),
    "cello":        ("strings", "cello", "Strings/cello"),
    "doublebass":   ("strings", "doublebass", "Strings/doublebass"),
    # 铜管
    "trumpet":      ("brass", "trumpet", "Brass/Bbtrumpet"),
    "frenchhorn":   ("brass", "frenchhorn", "Brass/frenchhorn"),
    "trombone":     ("brass", "trombone", "Brass/tenortrombone"),
    "tuba":         ("brass", "tuba", "Brass/tuba"),
    "saxophone":    ("brass", "saxophone", "Brass/altosaxophone"),
    # 木管
    "flute":        ("woodwind", "flute", "Woodwinds/flute"),
    "oboe":         ("woodwind", "oboe", "Woodwinds/oboe"),
    "clarinet":     ("woodwind", "clarinet", "Woodwinds/Bbclarinet"),
    "bassoon":      ("woodwind", "bassoon", "Woodwinds/bassoon"),
    # 键盘
    "piano":        ("keys", "piano", "Piano_Other/piano"),
}

_PAGE_OF = {
    "violin": "MISviolin", "viola": "MISviola", "cello": "MIScello",
    "doublebass": "MISdoublebass", "trumpet": "MISBbtrumpet",
    "frenchhorn": "MISFrenchhorn", "trombone": "MIStenortrombone",
    "tuba": "MIStuba", "saxophone": "MISaltosaxophone", "flute": "MISflute",
    "oboe": "MISoboe", "clarinet": "MISBbclarinet", "bassoon": "MISbassoon",
    "piano": "MISpiano",
}

LINK_RE = re.compile(r'href="(sound (?:files|%20files)/[^"]+\.aiff?)"', re.I)
NOTE_RE = re.compile(r"(?<![A-Za-z])([A-Ga-g])([#b]?)(\d)(?![0-9])")


def note_of(filename: str) -> str | None:
    """从文件名取**音级**（如 `Bb`）；只有单音样本才返回，范围样本返回 None。

    为什么区分：MIS 里除钢琴外都是"一条样本覆盖一段音域"，比如
    `Violin.arco.pp.sulG.G3B3.aiff` 表示覆盖 G3~B3，根音并不明确 ——
    按起点猜音级会污染 `--key` 的选音（宁可留空，让使用方知道不确定）。
    而 `Piano.ff.B5.aiff` 是明确的单音，音级就是 B。
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    found = NOTE_RE.findall(stem)
    if len(found) != 1:
        return None
    letter, accidental, _octave = found[0]
    return letter.upper() + accidental


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _abs_url(rel: str) -> str:
    """把页面里的相对链接变成可下载的绝对 URL（空格要编码）。"""
    rel = rel.replace("sound files/", "sound%20files/")
    return f"{BASE}/{urllib.parse.quote(rel, safe='/%')}"


def list_links(instrument: str) -> list[str]:
    page = _PAGE_OF[instrument]
    html = _get(f"{BASE}/{page}.html").decode("utf-8", "replace")
    links = LINK_RE.findall(html)
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for ln in links:
        if ln in seen:
            continue
        seen.add(ln)
        out.append(ln)
    return out


def _spread(items: list[str], n: int) -> list[str]:
    """从列表里等距取 n 条。

    为什么不是取前 n 条：页面是按力度/奏法分组的（pp 一串、mf 一串…），
    取前 n 会只拿到同一个力度、音域也偏在低音区。等距取能同时覆盖音域和力度。
    """
    if n <= 0 or n >= len(items):
        return list(items)
    step = len(items) / float(n)
    return [items[int(i * step)] for i in range(n)]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _duration_ms(path: str) -> int:
    """用 ffmpeg 解析时长（本机可能没有 ffprobe，不能依赖它）。"""
    ffmpeg = binfind.resolve("ffmpeg")
    if not ffmpeg:
        return 0
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-i", path],
                           capture_output=True, text=True, timeout=60)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr or "")
        if m:
            h, mi, s = m.groups()
            return int(round((int(h) * 3600 + int(mi) * 60 + float(s)) * 1000))
    except Exception:  # noqa: BLE001
        pass
    return 0


def download(rel: str, dest: str, retries: int = 3) -> int:
    """下载一条；已存在且非空则跳过，返回字节数（0 表示跳过）。"""
    if os.path.isfile(dest) and os.path.getsize(dest) > 1024:
        return 0
    url = _abs_url(rel)
    last = None
    for i in range(retries):
        try:
            data = _get(url, timeout=180)
            if len(data) < 1024:
                raise IOError(f"响应过小（{len(data)}B）")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            return len(data)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i + 1 < retries:
                time.sleep(1.5 * (i + 1))
    raise IOError(f"下载失败：{url}（{last}）")


def transcode(src: str, dst: str, sample_rate: int = 44100) -> None:
    """AIFF -> 44.1k/16bit WAV。保持原声道数（单音样本没必要硬上立体声）。"""
    ffmpeg = binfind.require("ffmpeg")
    p = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", src,
         "-acodec", "pcm_s16le", "-ar", str(sample_rate), dst],
        capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError(f"转码失败：{os.path.basename(src)}：{(p.stderr or '').strip()[:300]}")


def _indent_of(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(" "):
                    return max(1, len(line) - len(line.lstrip(" ")))
    except OSError:
        pass
    return 2


def load_manifest(pool_dir: str) -> dict:
    p = os.path.join(pool_dir, "manifest.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("entries"), list):
            d.setdefault("generated_by", "fetch_iowa_mis.py")
            return d
    return {"generated_by": "fetch_iowa_mis.py", "entries": []}


def save_manifest(pool_dir: str, data: dict, dry_run: bool = False) -> None:
    if dry_run:
        return
    p = os.path.join(pool_dir, "manifest.json")
    indent = _indent_of(p)
    data.setdefault("generated_by", "fetch_iowa_mis.py")
    data["last_ingested_by"] = "fetch_iowa_mis.py"
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, p)


def upsert(data: dict, entry: dict) -> str:
    """按 file 名 upsert；返回 'added' / 'updated'。"""
    for i, e in enumerate(data["entries"]):
        if e.get("file") == entry["file"]:
            data["entries"][i] = {**e, **entry}
            return "updated"
    data["entries"].append(entry)
    return "added"


def main() -> int:
    ap = argparse.ArgumentParser(description="抓爱荷华 MIS 单音采样，填乐器池")
    ap.add_argument("--root", default=os.environ.get("MUSICKIT_ROOT")
                    or os.path.dirname(_REMIX_DIR), help="素材根目录（默认仓根）")
    ap.add_argument("--instruments", nargs="*", default=["piano", "violin", "trumpet", "flute"],
                    help=f"乐器名（可多选）：{', '.join(sorted(PAGES))}")
    ap.add_argument("--limit", type=int, default=8, help="每个乐器最多下几条（0=全部）")
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "musickit_iowa"),
                    help="原始 AIFF 缓存目录")
    ap.add_argument("--sample-rate", type=int, default=44100)
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不下载不写盘")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载/转码")
    args = ap.parse_args()

    unknown = [i for i in args.instruments if i not in PAGES]
    if unknown:
        print(f"❌ 不认识的乐器：{unknown}\n   可选：{', '.join(sorted(PAGES))}", file=sys.stderr)
        return 2

    binfind.ensure_path_env()
    if not args.dry_run and not binfind.resolve("ffmpeg"):
        print("❌ 需要 ffmpeg 转码：请放入 remix/bin 或装到系统 PATH", file=sys.stderr)
        return 2

    os.makedirs(args.cache, exist_ok=True)
    total_added = total_updated = total_skip = total_fail = 0

    for inst in args.instruments:
        pool, subcat, subdir = PAGES[inst]
        pool_dir = os.path.join(args.root, pool)
        if not args.dry_run:
            os.makedirs(pool_dir, exist_ok=True)

        try:
            links = list_links(inst)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ {inst}: 抓页面失败 {exc}", file=sys.stderr)
            total_fail += 1
            continue
        picked = _spread(links, args.limit)
        print(f"\n== {inst} -> {pool}/{subcat}  （页面 {len(links)} 条，取 {len(picked)} 条）")
        if not picked:
            print("   ⚠ 页面里没找到 .aiff 链接，跳过")
            continue

        data = load_manifest(pool_dir) if not args.dry_run else {"entries": []}
        for rel in picked:
            base = os.path.basename(rel)
            stem, _ext = os.path.splitext(base)
            target_name = f"iowa__{stem}.wav"
            target = os.path.join(pool_dir, target_name)
            print(f"   - {base} -> {target_name}")

            if args.dry_run:
                continue

            exists = os.path.isfile(target)
            if exists and not args.force:
                # 不重下，但仍刷新 manifest 元数据 —— 否则早先下的条目永远补不上 key
                print("     已存在，仅刷新 manifest 元数据")
                total_skip += 1
            else:
                cached = os.path.join(args.cache, inst, base)
                try:
                    got = download(rel, cached)
                    if got:
                        print(f"     下载 {got / 1048576:.1f}MB")
                    tmp_wav = os.path.join(args.cache, inst, stem + ".wav")
                    if not os.path.isfile(tmp_wav) or args.force:
                        transcode(cached, tmp_wav, args.sample_rate)
                    shutil.move(tmp_wav, target)
                except Exception as exc:  # noqa: BLE001
                    print(f"     ❌ {exc}", file=sys.stderr)
                    total_fail += 1
                    continue

            dur_ms = _duration_ms(target)
            entry = {
                "file": target_name,
                "subcategory": subcat,
                "source_pack": SOURCE_PACK,
                "original": base,
                "original_rel": subdir,
                "license": LICENSE_TEXT,
                "license_tier": "free",
                "content_kind": "oneshot",
                "duration_s": round(dur_ms / 1000.0, 2) if dur_ms else None,
                "sha256": _sha256(target),
                "source_url": _abs_url(rel),
                "fetched_at": time.strftime("%Y-%m-%d"),
            }
            note = note_of(base)
            if note:
                # 单音：音级确定但调式无意义 → 标记 pitch_only，选音时按音级比较。
                # 同时把可能残留的 chroma 结果清掉（scale/margin 来自 detect_keys）：
                # 留着会变成「文件名的音级 + 别人测的调式」这种谁也没测出来的混合信息。
                entry["key"] = note
                entry["key_pitch_only"] = True
                entry["key_source"] = "filename"
                entry["key_confidence"] = 1.0
                entry["scale"] = None
                entry["key_margin"] = None
            action = upsert(data, entry)
            if action == "added":
                total_added += 1
            else:
                total_updated += 1

        if not args.dry_run:
            save_manifest(pool_dir, data)
            print(f"   manifest 已更新：{os.path.join(pool_dir, 'manifest.json')}"
                  f"（{len(data['entries'])} 条）")

    print(f"\n完成：新增 {total_added} / 更新 {total_updated} / 跳过 {total_skip} / 失败 {total_fail}")
    if total_fail:
        print("⚠ 有失败项，可重跑（已下载的会跳过）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
