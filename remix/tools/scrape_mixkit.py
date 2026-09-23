"""Mixkit 免费音效抓取：动物叫声（vocal 替代层）+ SFX（riser/impact 过渡层）。

Mixkit License：个人/商用均免费，不可原样转售音效本身 —— 符合素材入库政策。
下载 URL 规律：https://assets.mixkit.co/active_storage/sfx/<id>/<id>.wav
用法: python scrape_mixkit.py [--limit 60]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

DOWNLOADS = str(_MK_ROOT / "archived" / "downloads")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 类别 → 去向子目录（vocal 层 / sfx 层）
CATEGORIES = {
    "animals": "mixkit_animals",      # 动物叫声 → vocal 替代层
    "riser": "mixkit_sfx",            # 上冲过渡
    "impact": "mixkit_sfx",           # 重击
    "transition": "mixkit_sfx",       # 过渡
    "whoosh": "mixkit_sfx",           # 呼啸
    "sweep": "mixkit_sfx",            # 扫频
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse_page(html: str) -> list[tuple[str, str]]:
    """从列表页提取 (id, title) 配对。"""
    cards = re.split(r'item-grid__item', html)
    pairs = []
    for card in cards:
        m_id = re.search(r'data-audio-player-item-id-value="(\d+)"', card)
        m_title = re.search(r'item-grid-card__title">\s*([^<]{2,100})', card)
        if m_id and m_title:
            pairs.append((m_id.group(1), re.sub(r"\s+", " ", m_title.group(1)).strip()))
    return pairs


def download(id_: str, title: str, dst_dir: str, delay: float = 1.0, retries: int = 3) -> bool:
    safe = re.sub(r'[^\w\-]+', "_", title)[:60]
    out_wav = os.path.join(dst_dir, f"{id_}_{safe}.wav")
    out_mp3 = os.path.join(dst_dir, f"{id_}_{safe}.mp3")
    if (os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000) or \
       (os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000):
        return True
    # 部分资产 .wav 返回 403，但 .mp3 可下载 —— 逐个尝试
    variants = [(f"{id_}.wav", out_wav, b"RIFF"), (f"{id_}.mp3", out_mp3, b"")]
    for attempt in range(1, retries + 1):
        for fname, out, magic in variants:
            url = f"https://assets.mixkit.co/active_storage/sfx/{id_}/{fname}"
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://mixkit.co/",
                })
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if len(data) < 1000 or (magic and not data[:4] == magic):
                    continue
                with open(out, "wb") as f:
                    f.write(data)
                if delay:
                    time.sleep(delay)
                return True
            except Exception:
                continue
        time.sleep(delay * attempt * 3)  # 退避后整体重试
    print(f"  [fail] {id_} {title}: 所有格式均失败", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60, help="每类最多下载数")
    ap.add_argument("--cats", type=str, default="", help="只抓指定类目（逗号分隔，默认全部）")
    ap.add_argument("--delay", type=float, default=1.0, help="每个文件下载间隔秒数（限流退避）")
    ap.add_argument("--retries", type=int, default=3, help="失败重试次数")
    args = ap.parse_args()

    cats = {c: CATEGORIES[c] for c in (args.cats.split(",") if args.cats else CATEGORIES)
            if c in CATEGORIES}
    total_ok = 0
    for cat, sub in cats.items():
        dst = os.path.join(DOWNLOADS, sub)
        os.makedirs(dst, exist_ok=True)
        got = 0
        page = 1
        seen = set()
        while got < args.limit and page <= 6:
            url = f"https://mixkit.co/free-sound-effects/{cat}/?page={page}"
            try:
                html = fetch(url)
            except Exception as e:
                print(f"[{cat}] 第 {page} 页失败: {e}")
                break
            pairs = parse_page(html)
            new = [(i, t) for i, t in pairs if i not in seen]
            if not new:
                break
            for i, t in new:
                if got >= args.limit:
                    break
                seen.add(i)
                if download(i, t, dst, delay=args.delay, retries=args.retries):
                    got += 1
            page += 1
        total_ok += got
        print(f"[{cat}] 已下载 {got} 个 → {dst}")
    print(f"合计 {total_ok} 个（Mixkit License：个人/商用免费，勿转售音效本体）")


if __name__ == "__main__":
    main()
