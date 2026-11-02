"""fetch_freepd — 从 freepd.cn 抓取公共领域（CC0）音乐，供 demucs 分离成 stem。

站点特征（2026-11-02 实测）：
  - 服务端渲染，无需 JS；
  - 下载直链形如 `https://freepd.cn/api/music/<hex(相对路径)>`，
    例如 `436f6d6564792f416c6c73204661697220496e204c6f76652e6d7033`
    解码为 `Comedy/Alls Fair In Love.mp3`；
  - 支持 Range，Content-Type: audio/mpeg；
  - 页面明确标注「公共领域（CC0）免费下载」。

用法：
  python remix/tools/fetch_freepd.py --out D:/tmp/freepd_src --limit 4
  python remix/tools/fetch_freepd.py --out ... --match love        # 只取曲名含 love 的
  python remix/tools/fetch_freepd.py --out ... --list              # 只列出，不下载

说明：
  - 仅抓 `/music` 首页可见的曲目（当前为 Comedy 分类，46 首）；
  - 已存在且大小一致则跳过（可重跑）；
  - 下载的是**整曲混音**，不能直接进 bass/drum/guita 池 —— 需先经
    `remix/tools/ingest_stems.py` 用 demucs 分离。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

BASE = "https://freepd.cn"
UA = {"User-Agent": "Mozilla/5.0 (compatible; musickit-fetch/1.0)"}


def fetch_page(path: str = "/music") -> str:
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse_tracks(html: str) -> list[tuple[str, str, str]]:
    """返回 [(相对下载路径, 解码后的源相对路径, 标题), ...]。"""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for rel, hexname, title in re.findall(
        r'href="(/api/music/([0-9a-fA-F]+))"\s+download="([^"]+)"', html
    ):
        if hexname in seen:
            continue
        seen.add(hexname)
        try:
            decoded = bytes.fromhex(hexname).decode("utf-8")
        except Exception:  # noqa: BLE001
            decoded = ""
        out.append((rel, decoded, title))
    return out


def _remote_size(rel: str, timeout: int = 30) -> int:
    """HEAD 取远端大小；失败返回 -1。"""
    try:
        req = urllib.request.Request(BASE + rel, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.headers.get("Content-Length") or -1)
    except Exception:  # noqa: BLE001
        return -1


def download(rel: str, dest: str, timeout: int = 300) -> int:
    """下载单个曲目；已存在且大小一致则跳过（返回 0 表示跳过）。"""
    if os.path.isfile(dest):
        local = os.path.getsize(dest)
        remote = _remote_size(rel, timeout=min(timeout, 30))
        if remote > 0 and local == remote:
            return 0
    req = urllib.request.Request(BASE + rel, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    return len(data)


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 freepd.cn 公版音乐（CC0）")
    ap.add_argument("--out", required=False, help="落盘目录")
    ap.add_argument("--limit", type=int, default=0, help="最多下载 N 首（0=全部）")
    ap.add_argument("--match", default="", help="只取标题包含该子串的（不区分大小写）")
    ap.add_argument("--list", action="store_true", help="只列出可用曲目")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    html = fetch_page()
    tracks = parse_tracks(html)
    print(f"页面解析到 {len(tracks)} 首")

    if args.match:
        tracks = [t for t in tracks if args.match.lower() in t[2].lower()]
        print(f"--match '{args.match}' 过滤后 {len(tracks)} 首")

    if args.list:
        for rel, decoded, title in tracks:
            print(f"  {title}   [{decoded}]")
        return 0

    if not args.out:
        print("❌ 下载模式需要 --out", file=sys.stderr)
        return 2
    if args.limit > 0:
        tracks = tracks[: args.limit]

    os.makedirs(args.out, exist_ok=True)
    ok = skip = fail = 0
    for rel, decoded, title in tracks:
        safe = re.sub(r'[<>:"/\\|?*]+', "_", title).strip() or "track.mp3"
        if not os.path.splitext(safe)[1]:
            safe += ".mp3"
        dst = os.path.join(args.out, safe)
        try:
            size = download(rel, dst, args.timeout)
            if size == 0:
                print(f"  ⏭️  {safe}（已存在，大小一致，跳过）")
                skip += 1
                continue
            print(f"  ✅ {safe}  ({size/1024/1024:.1f} MB)  ← {decoded}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {safe}: {type(e).__name__}: {e}", file=sys.stderr)
            fail += 1

    print(f"\n完成：下载 {ok} / 跳过 {skip} / 失败 {fail} → {args.out}")
    print("下一步：python remix/tools/ingest_stems.py --src <上面目录> --source-tag freepd")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
