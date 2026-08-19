#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地混音师电台 —— MUBERT_COMPARISON.md L2

把 24 位混音师签名链包装成「风格频道」的本地电台形态：
  同一频道 = 固定混音师 + 随机流派提示词 + 随机 stems
  → 频道内一致性（同一调音台签名）、曲目间新鲜感（随机素材），对齐 Mubert 频道体验。

用法：
  python mixer_radio.py --list
  python mixer_radio.py --channel wallace --count 3
  python mixer_radio.py --channel joshua --max-minutes 30 --format mp3
  python mixer_radio.py --channel random --count 5 --seed 42 --category phonk
  python mixer_radio.py --channel ali --count 2 --release-safe

输出：--out 目录下的曲目文件 + <slug>_radio.m3u8 播放列表（顺序播放即电台）+ radio_report.json。
依赖：F:/Python314（与 remix 引擎一致，pydub + numpy/scipy/soundfile + 内置 ffmpeg）。
"""
import argparse
import json
import os
import random
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MUSICKIT_ROOT = os.environ.get("MUSICKIT_ROOT") or os.path.dirname(os.path.dirname(_THIS_DIR))
os.environ["MUSICKIT_ROOT"] = MUSICKIT_ROOT
MUSIC_DIR = os.path.join(MUSICKIT_ROOT, "music")
REMIX_DIR = os.path.join(MUSICKIT_ROOT, "remix")
BURB_DIR = os.path.join(MUSICKIT_ROOT, "burbidge_album")

sys.path.insert(0, MUSIC_DIR)
sys.path.insert(0, REMIX_DIR)
sys.path.insert(0, BURB_DIR)

import mixer_styles as MS          # noqa: E402
import prompt_driven_remix as pdr  # noqa: E402  复用提示词→混音映射与引擎桥

DEFAULT_OUT = os.path.join(MUSICKIT_ROOT, "remix", "output", "mixer_radio")


def banner(st):
    print("=" * 64)
    print(f"  📻 {st['name']}（{st['zh']}）电台  ·  {st['tagline']}")
    print(f"  {st['about']}")
    print(f"  参考艺人：{', '.join(st['refs'])}")
    print("=" * 64)


def main():
    p = argparse.ArgumentParser(
        description="本地混音师电台：固定混音师签名 + 随机流派提示词，连续产出并生成播放列表",
    )
    p.add_argument("--list", action="store_true", help="列出全部频道（24 位混音师）")
    p.add_argument("--channel", type=str, default="random",
                   help="频道 slug（见 --list；random = 每曲随机一位混音师）")
    p.add_argument("--category", type=str, default=None,
                   help="固定流派风格 key（如 phonk/lofi/rnb；默认随机 65 流派）")
    p.add_argument("--fusion", action="store_true", help="提示词跨类融合（增加新鲜感）")
    p.add_argument("--count", type=int, default=None, help="产出曲目数（默认 3）")
    p.add_argument("--max-minutes", type=float, default=None,
                   help="按总时长产出（分钟，与 --count 二者先到即停）")
    p.add_argument("--bars", type=int, default=32, help="每曲小节数（默认 32）")
    p.add_argument("--format", type=str, default="mp3", choices=["wav", "mp3", "ogg", "flac"])
    p.add_argument("--out", type=str, default=DEFAULT_OUT, help="输出目录")
    p.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    p.add_argument("--max-tracks", type=int, default=5, help="单曲最大音轨数（默认 5，上限 8）")
    p.add_argument("--no-skeleton", action="store_true", help="不为缺失鼓/贝斯自动补骨架")
    p.add_argument("--release-safe", action="store_true", help="仅用 free/pack 授权素材")
    args = p.parse_args()

    if args.list:
        print(f"共 {len(MS.STYLES)} 个频道（slug → 混音师）：")
        for st in MS.STYLES:
            print(f"  {st['slug']:<12} {st['name']:<18} {st['zh']:<10} {st['tagline']}")
        return

    if args.count is None and args.max_minutes is None:
        args.count = 3

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)
    slug = args.channel if args.channel != "random" else rng.choice(MS.SLUGS)
    if slug not in MS.STYLE_BY_SLUG:
        raise SystemExit(f"未知频道 '{slug}'，可用：{', '.join(MS.SLUGS)} / random（--list 查看）")
    banner(MS.STYLE_BY_SLUG[slug])

    m3u_path = os.path.join(args.out, f"{slug}_radio.m3u8")
    m3u = ["#EXTM3U", f"# {slug} radio - {MS.STYLE_BY_SLUG[slug]['name']}"]
    report = []
    n = 0
    total_s = 0.0
    t0 = time.time()

    while True:
        if args.count is not None and n >= args.count:
            break
        if args.max_minutes is not None and total_s >= args.max_minutes * 60.0:
            break
        cur = slug if slug != "random" else rng.choice(MS.SLUGS)
        st = MS.STYLE_BY_SLUG[cur]
        data = pdr.generate_prompts(1, args.category, fusion=args.fusion, seed=None)[0]
        mp = pdr.prompt_to_mix_params(data, rng,
                                      max_tracks=args.max_tracks,
                                      add_skeleton=not args.no_skeleton,
                                      release_safe=args.release_safe)
        out = pdr.run_remix(count=len(mp["tracks"]), seed=args.seed, out_dir=args.out,
                            fmt=args.format, bars=args.bars, bpm=mp["bpm"],
                            structure=mp["structure"], tracks=mp["tracks"],
                            release_safe=args.release_safe, mixer_style=cur)
        dur_s = 0.0
        try:
            dur_s = pdr._m.duration_ms(out) / 1000.0
        except Exception:
            pass
        n += 1
        total_s += dur_s
        m3u.append(f"#EXTINF:{int(dur_s)},{st['name']} - {data.get('label', '')} ({data.get('subgenre', '')})")
        m3u.append(os.path.basename(out))
        report.append({"n": n, "channel": cur, "label": data.get("label", ""),
                       "subgenre": data.get("subgenre", ""), "sentence": data.get("sentence", ""),
                       "bpm": mp["bpm"], "structure": mp["structure"],
                       "duration_s": round(dur_s, 1), "output": out})
        print(f"[#{n}] {cur:<12} {data.get('label', ''):<24} {mp['bpm']} BPM  "
              f"{dur_s:.0f}s  -> {os.path.basename(out)}")

    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")
    with open(os.path.join(args.out, "radio_report.json"), "w", encoding="utf-8") as f:
        json.dump({"channel": slug, "tracks": report,
                   "total_s": round(total_s, 1), "elapsed_s": round(time.time() - t0, 1)},
                  f, ensure_ascii=False, indent=2)
    print(f"\n📻 完成 {n} 曲，共 {total_s:.0f}s，用时 {time.time() - t0:.0f}s")
    print(f"   播放列表：{m3u_path}")
    print(f"   报告：{os.path.join(args.out, 'radio_report.json')}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
