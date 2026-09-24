#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""musickit 单曲随机渲染器 —— 供电台/外部服务按需调用

把「随机渲染」封装成一个进程：渲染一首随机混音（随机混音师签名 +
随机流派提示词 + 随机 stems），把结果写到 --out 目录，并向 stdout
输出一行 JSON 元数据，方便调用方（如 <MUSICKIT_ROOT>\\radio 电台的
musickit_source）直接消费。

用法：
  python musickit_render_one.py --channel random --bars 32 --format mp3 --out <输出目录>
  python musickit_render_one.py --channel wallace --category phonk --seed 42 --release-safe

输出（stdout，成功时 exit 0）：
  {"ok": true, "file": "<绝对路径>", "channel": "wallace", "style": "Wallace",
   "label": "phonk", "subgenre": "memphis", "bpm": 140, "duration_s": 42.3}

失败时 exit 1 并输出 {"ok": false, "error": "..."}。
依赖：与 remix 引擎一致（pydub + numpy + scipy + soundfile + audioop-lts）。
"""
import argparse
import json
import os
import random
import sys

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
import prompt_driven_remix as pdr  # noqa: E402


def render_one(channel, category, fusion, bars, fmt, out_dir, seed,
               max_tracks, no_skeleton, release_safe):
    rng = random.Random(seed)
    slug = channel if channel != "random" else rng.choice(MS.SLUGS)
    if slug not in MS.STYLE_BY_SLUG:
        raise ValueError(f"未知频道 '{slug}'，可用：{', '.join(MS.SLUGS)} / random")

    st = MS.STYLE_BY_SLUG[slug]
    data = pdr.generate_prompts(1, category, fusion=fusion, seed=seed)[0]
    mp = pdr.prompt_to_mix_params(data, rng,
                                  max_tracks=max_tracks,
                                  add_skeleton=not no_skeleton,
                                  release_safe=release_safe)
    out = pdr.run_remix(count=len(mp["tracks"]), seed=seed, out_dir=out_dir,
                        fmt=fmt, bars=bars, bpm=mp["bpm"],
                        structure=mp["structure"], tracks=mp["tracks"],
                        release_safe=release_safe, mixer_style=slug)
    dur_s = 0.0
    try:
        dur_s = float(pdr._m.duration_ms(out)) / 1000.0
    except Exception:
        pass
    return {
        "file": os.path.abspath(out),
        "channel": slug,
        "style": st.get("name", slug),
        "style_zh": st.get("zh", ""),
        "label": data.get("label", ""),
        "subgenre": data.get("subgenre", ""),
        "bpm": mp.get("bpm"),
        "bars": bars,
        "duration_s": round(dur_s, 2),
    }


def main():
    ap = argparse.ArgumentParser(description="musickit 单曲随机渲染器")
    ap.add_argument("--channel", type=str, default="random",
                    help="混音师频道 slug；random = 每曲随机一位（默认）")
    ap.add_argument("--category", type=str, default=None,
                    help="固定流派风格 key（默认随机 65 流派）")
    ap.add_argument("--fusion", action="store_true", help="提示词跨类融合")
    ap.add_argument("--bars", type=int, default=32, help="每曲小节数（默认 32）")
    ap.add_argument("--format", type=str, default="mp3", choices=["wav", "mp3", "ogg", "flac"])
    ap.add_argument("--out", type=str, required=True, help="输出目录（自动创建）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    ap.add_argument("--max-tracks", type=int, default=5, help="单曲最大音轨数（默认 5）")
    ap.add_argument("--no-skeleton", action="store_true", help="不为缺失鼓/贝斯自动补骨架")
    ap.add_argument("--release-safe", action="store_true", help="仅用 free/pack 授权素材")
    args = ap.parse_args()

    try:
        os.makedirs(args.out, exist_ok=True)
        result = render_one(args.channel, args.category, args.fusion, args.bars,
                            args.format, args.out, args.seed, args.max_tracks,
                            args.no_skeleton, args.release_safe)
        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
