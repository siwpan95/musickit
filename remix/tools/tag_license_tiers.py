#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""给 13 个素材池的 manifest 条目补齐 license_tier 与缺失的 license 文案。

tier 语义（引擎 --release-safe 只放行 free/pack）：
  free       — 可免费商用/发布的素材（Mixkit、MusicRadar SampleRadar 等）
  pack       — 商业采样包：按包 EULA 可用于音乐制作与发布成品，样本本身勿转售
  restricted — 商业歌曲 Demucs 分离 stem / 粉丝提取游戏音乐：仅个人练习与研究，勿发布
  unknown    — 来源未记录：--release-safe 一律剔除

判定规则（按顺序首中即停）：
  1) license 含 MusicRadar SampleRadar / Mixkit → free
  2) source_pack == csmusic 或 license 含「粉丝提取」→ restricted
  3) source_pack == sync → 按池默认（acapella=pack / cowbell=free / 其余 unknown）
  4) source_pack 为空且文件名为整曲 stem 命名（bass (N).wav 等）→ restricted（radio stem）
  5) license 含 commercial sample pack，或 source_pack 属已知商业包 → pack
  6) 其余 → unknown

用法：
  python tag_license_tiers.py --root G:\music\musickit            # dry-run：只打印计划分布
  python tag_license_tiers.py --root G:\music\musickit --apply    # 备份并原地改写 manifest
"""
import argparse
import json
import os
import re
import shutil
from collections import Counter

POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]

STEM_RE = re.compile(r"^(bass|drum|guita) \(\d{1,3}\)\.(wav|mp3|flac|aiff|aif)$", re.I)

COMMERCIAL_PACKS = [
    "black octopus", "industrial strength", "sakura", "singomakers",
    "function loops", "loopmasters", "producer loops", "kryptic samples",
    "xam", "coollider",
]

# MusicRadar SampleRadar 免费包（source_pack 命名；部分条目 license 字段为空，需补）
FREE_SAMPLERADAR_PACKS = [
    "ebm", "deep_house", "funk_keys", "hiphop90s",
    "processed_guitar188", "guitar_bass272",
]

LICENSE_TEXTS = {
    "coollider": "Coollider Acapellas Vol.1-42（商业包；EULA 允许音乐制作使用，勿转售样本；含知名原唱歌曲，对外发布请自行评估原曲权利）",
    "mixkit": "Mixkit License (personal/commercial free; do not redistribute the SFX as-is)",
    "radio_stem": "Demucs 分离自商业歌曲（仅个人练习/研究，勿发布成品）",
    "commercial_pack": "Royalty-free (commercial sample pack; verify EULA, do not redistribute)",
    "unknown": "来源未记录（--release-safe 将剔除）",
    "unknown_library": "来源未记录（疑似本地乐器音色库单音采样，--release-safe 将剔除）",
}


def classify(pool: str, e: dict) -> tuple[str, str | None]:
    """返回 (tier, license_text)。license_text 为 None 表示沿用原 license。"""
    license_str = (e.get("license") or "").strip()
    pack = (e.get("source_pack") or "").strip()
    fname = e.get("file") or ""

    if "MusicRadar SampleRadar" in license_str or "Mixkit" in license_str:
        return "free", None
    if pack.lower() == "csmusic" or "粉丝提取" in license_str:
        return "restricted", None
    if pack.lower() == "sync":
        if pool == "acapella":
            return "pack", LICENSE_TEXTS["coollider"]
        if pool == "cowbell":
            return "free", LICENSE_TEXTS["mixkit"]
        if pool in ("woodwind", "keys", "strings", "brass"):
            return "unknown", LICENSE_TEXTS["unknown_library"]
        return "unknown", LICENSE_TEXTS["unknown"]
    if not pack:
        if STEM_RE.match(fname):
            return "restricted", LICENSE_TEXTS["radio_stem"]
        return "unknown", LICENSE_TEXTS["unknown"]
    if pack.lower() in FREE_SAMPLERADAR_PACKS:
        return "free", "Royalty-free (MusicRadar SampleRadar)"
    if "commercial sample pack" in license_str or \
            any(p in pack.lower() for p in COMMERCIAL_PACKS):
        if pack.lower() == "coollider":
            return "pack", LICENSE_TEXTS["coollider"]
        return "pack", (license_str or LICENSE_TEXTS["commercial_pack"])
    return "unknown", (license_str or LICENSE_TEXTS["unknown"])


def process_pool(root: str, pool: str, apply: bool) -> Counter:
    mp = os.path.join(root, pool, "manifest.json")
    if not os.path.isfile(mp):
        return Counter({"missing_manifest": 1})
    with open(mp, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return Counter({"bad_manifest": 1})

    dist = Counter()
    for e in data["entries"]:
        if not isinstance(e, dict):
            continue
        tier, text = classify(pool, e)
        dist[tier] += 1
        if apply:
            if text is not None:
                e["license"] = text
            e["license_tier"] = tier

    if apply:
        backup_dir = os.path.join(root, "archived", "manifest_backup_20260817")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(mp, os.path.join(backup_dir, f"{pool}_manifest.json"))
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return dist


def main():
    p = argparse.ArgumentParser(description="license_tier 标注与 license 补全")
    p.add_argument("--root", default=r"G:\music\musickit", help="musickit 根目录")
    p.add_argument("--apply", action="store_true",
                   help="备份（archived/manifest_backup_20260817/）并原地改写 manifest")
    args = p.parse_args()

    total = Counter()
    print(f"{'pool':<10} {'free':>6} {'pack':>6} {'restricted':>10} {'unknown':>8}")
    for pool in POOLS:
        dist = process_pool(args.root, pool, args.apply)
        total.update(dist)
        print(f"{pool:<10} {dist['free']:>6} {dist['pack']:>6} "
              f"{dist['restricted']:>10} {dist['unknown']:>8}")
    print("-" * 46)
    print(f"{'TOTAL':<10} {total['free']:>6} {total['pack']:>6} "
          f"{total['restricted']:>10} {total['unknown']:>8}")
    print("\n模式：" + ("已写入（备份在 archived/manifest_backup_20260817/）" if args.apply
                       else "dry-run（加 --apply 落盘）"))


if __name__ == "__main__":
    main()
