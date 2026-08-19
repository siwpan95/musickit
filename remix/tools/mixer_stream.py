#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地混音师流服务 —— MUBERT_COMPARISON.md L3

把 24 位混音师频道做成本地无限流（类 Mubert 频道形态，零外部依赖，仅标准库）：
  GET /                     频道主页（24 张卡片 + <audio> 直接播放）
  GET /api/channels         频道目录 JSON
  GET /api/stream/<slug>    无限流：连续 MP3 帧 chunked 输出（浏览器/VLC 即点即播）
  GET /api/track/<slug>?seed=N&bars=32   单曲生成并下载
  GET /api/playlist/<slug>  m3u 播放列表（指向 stream 端点）

用法：
  python mixer_stream.py [--port 8010] [--bars 32] [--release-safe]
依赖：F:/Python314（与 remix 引擎一致）；引擎经内置 ffmpeg 输出 mp3。
频道一致性 = 固定混音师签名链；新鲜感 = 随机流派提示词 + 随机 stems（fusion 增强）。
"""
import argparse
import json
import os
import queue
import random
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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

OUT_DIR = os.path.join(REMIX_DIR, "output", "mixer_stream")

_WORKERS = {}
_LOCK = threading.Lock()


class ChannelWorker(threading.Thread):
    """每频道一个后台线程：连续渲染该混音师签名的曲目进队列（深度 3）。"""

    def __init__(self, slug, bars, release_safe):
        super().__init__(daemon=True, name=f"channel-{slug}")
        self.slug = slug
        self.bars = bars
        self.release_safe = release_safe
        self.q = queue.Queue(maxsize=3)
        self.started_at = time.time()

    def run(self):
        rng = random.Random()
        os.makedirs(OUT_DIR, exist_ok=True)
        while True:
            st = MS.STYLE_BY_SLUG[self.slug]
            data = pdr.generate_prompts(1, None, fusion=True, seed=None)[0]
            mp = pdr.prompt_to_mix_params(data, rng, max_tracks=5,
                                          add_skeleton=True, release_safe=self.release_safe)
            out = pdr.run_remix(count=len(mp["tracks"]), seed=None, out_dir=OUT_DIR,
                                fmt="mp3", bars=self.bars, bpm=mp["bpm"],
                                structure=mp["structure"], tracks=mp["tracks"],
                                release_safe=self.release_safe, mixer_style=self.slug)
            self.q.put({"label": data.get("label", ""), "subgenre": data.get("subgenre", ""),
                        "bpm": mp["bpm"], "out": out})


def get_worker(slug, bars, release_safe):
    with _LOCK:
        w = _WORKERS.get(slug)
        if w is None:
            w = ChannelWorker(slug, bars, release_safe)
            _WORKERS[slug] = w
            w.start()
        return w


INDEX_HTML = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>musickit 混音师电台 · 本地流</title>
<style>
 body{margin:0;background:#0c0a0d;color:#e8e0d2;font-family:Helvetica,Arial,sans-serif}
 .wrap{max-width:820px;margin:0 auto;padding:28px 18px 60px}
 h1{font-family:Georgia,serif;font-style:italic;color:#f3e2bd;text-align:center;font-size:28px}
 .tag{text-align:center;letter-spacing:4px;color:#d9a441;font-size:12px;margin-bottom:22px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
 .card{background:#141013;border:1px solid #26211c;border-radius:8px;padding:14px}
 .cname{font-family:Georgia,serif;color:#f0e8da;font-size:16px}
 .czh{color:#9c8e74;font-size:12px;margin:2px 0 6px}
 .ctag{color:VARCOLOR;font-size:11.5px;line-height:1.5;margin-bottom:8px}
 audio{width:100%;height:32px}
 .link{display:block;font-size:11px;color:#6f6555;margin-top:8px;text-decoration:none}
 .link:hover{color:#d9a441}
</style></head>
<body><div class="wrap">
<h1>musickit 混音师电台</h1>
<div class="tag">24 CHANNELS · FIXED MIXER SIGNATURE × RANDOM STEMS</div>
<div class="grid">
CARDS
</div>
<p style="text-align:center;color:#6f6555;font-size:12px;margin-top:26px">
点播放即开始该频道无限流（本地渲染，首曲约 15~25 秒起播）。API：/api/channels · /api/stream/&lt;slug&gt; · /api/track/&lt;slug&gt;?seed=N</p>
</div></body></html>"""


def index_html():
    cards = []
    for st in MS.STYLES:
        cards.append(
            f'<div class="card"><div class="cname">{st["name"]}</div>'
            f'<div class="czh">{st["zh"]}</div>'
            f'<div class="ctag" style="color:{st["color"]}">{st["tagline"]}</div>'
            f'<audio controls preload="none" src="/api/stream/{st["slug"]}"></audio>'
            f'<a class="link" href="/api/track/{st["slug"]}?seed=1">单曲下载</a>'
            f'<a class="link" href="/api/playlist/{st["slug"]}">m3u</a></div>')
    return INDEX_HTML.replace("CARDS", "\n".join(cards))


class Handler(BaseHTTPRequestHandler):
    server_version = "mixer_stream/1.0"

    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[stream] %s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, content_type="audio/mpeg", attachment=None):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(body)

    def _slug(self):
        parts = self.path.split("?")[0].strip("/").split("/")
        return parts[-1] if parts else ""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        q = urllib.parse.parse_qs(parsed.query)

        if path == "" or path == "/index.html":
            body = index_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/channels":
            self._json({"channels": [{"slug": st["slug"], "name": st["name"],
                                      "zh": st["zh"], "color": st["color"],
                                      "tagline": st["tagline"], "refs": st["refs"],
                                      "target_lufs": st["target_lufs"]}
                                     for st in MS.STYLES]})
            return

        if path.startswith("/api/stream/"):
            slug = self._slug()
            if slug not in MS.STYLE_BY_SLUG:
                return self._json({"error": f"unknown channel {slug}"}, 404)
            worker = get_worker(slug, self.server.bars, self.server.release_safe)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            # 连续 MP3 帧输出：逐块写出，客户端可边播边收
            while True:
                try:
                    meta = worker.q.get(timeout=90)
                except queue.Empty:
                    break
                try:
                    with open(meta["out"], "rb") as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                sys.stderr.write(f"[stream] {slug} 已推流: {os.path.basename(meta['out'])} "
                                 f"({meta['label']}, {meta['bpm']} BPM)\n")
            return

        if path.startswith("/api/track/"):
            slug = self._slug()
            if slug not in MS.STYLE_BY_SLUG:
                return self._json({"error": f"unknown channel {slug}"}, 404)
            seed = int(q.get("seed", ["1"])[0])
            bars = int(q.get("bars", [str(self.server.bars)])[0])
            rng = random.Random(seed)
            st = MS.STYLE_BY_SLUG[slug]
            data = pdr.generate_prompts(1, None, fusion=True, seed=seed)[0]
            mp = pdr.prompt_to_mix_params(data, rng, max_tracks=5, add_skeleton=True,
                                          release_safe=self.server.release_safe)
            out = pdr.run_remix(count=len(mp["tracks"]), seed=seed, out_dir=OUT_DIR,
                                fmt="mp3", bars=bars, bpm=mp["bpm"],
                                structure=mp["structure"], tracks=mp["tracks"],
                                release_safe=self.server.release_safe, mixer_style=slug)
            return self._file(out, attachment=f"{slug}_seed{seed}.mp3")

        if path.startswith("/api/playlist/"):
            slug = self._slug()
            if slug not in MS.STYLE_BY_SLUG:
                return self._json({"error": f"unknown channel {slug}"}, 404)
            host = self.headers.get("Host", "127.0.0.1:8010")
            st = MS.STYLE_BY_SLUG[slug]
            body = (f"#EXTM3U\n#EXTINF:-1,{st['name']} - {st['tagline']} (infinite)\n"
                    f"http://{host}/api/stream/{slug}\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "audio/x-mpegurl")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self._json({"error": "not found", "help": "/api/channels /api/stream/<slug> "
                    "/api/track/<slug>?seed=N /api/playlist/<slug>"}, 404)


def main():
    ap = argparse.ArgumentParser(description="本地混音师流服务（类 Mubert 频道无限流）")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--host", type=str, default="127.0.0.1")
    ap.add_argument("--bars", type=int, default=32, help="流内每曲小节数（默认 32）")
    ap.add_argument("--release-safe", action="store_true", help="仅用 free/pack 授权素材")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.bars = args.bars
    srv.release_safe = args.release_safe
    print("=" * 64)
    print(f"  📡 musickit 混音师流服务   http://{args.host}:{args.port}/")
    print(f"  频道页      http://{args.host}:{args.port}/")
    print(f"  频道目录    http://{args.host}:{args.port}/api/channels")
    print(f"  无限流      http://{args.host}:{args.port}/api/stream/<slug>")
    print(f"  单曲下载    http://{args.host}:{args.port}/api/track/<slug>?seed=1&bars=32")
    print(f"  播放列表    http://{args.host}:{args.port}/api/playlist/<slug>")
    print(f"  频道 slug：{', '.join(MS.SLUGS)}")
    print("=" * 64)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[stream] 停止服务")
        srv.shutdown()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
