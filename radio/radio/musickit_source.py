"""musickit 随机渲染源 —— 用 musickit 的随机渲染代替本地 music/ 歌单。

工作方式：
  - 一个后台线程反复调用 musickit 的单曲渲染器（remix/tools/musickit_render_one.py），
    把渲染好的 MP3 放进缓存目录，并维护一个深度有限的就绪队列；
  - 广播者（broadcaster）在 mode == "musickit" 时从队列取下一首推送，
    与本地歌单共用同一套推流/ICY/HLS/录音管线；
  - 渲染是子进程（默认当前解释器，可用 MUSICKIT_RENDER_PYTHON 覆盖），
    引擎崩溃不会带垮电台主进程。

缓存管理：只清理本模块自己渲染的文件，按渲染时间保留最近
MUSICKIT_RENDER_KEEP 个，其余删除。
"""
import json
import os
import queue
import subprocess
import threading
import time
import sys

from . import config


def _renderer_path():
    """定位 musickit 单曲渲染器（合并后 remix/tools 与电台同在一个仓库）。"""
    p = os.path.join(config.MUSICKIT_ROOT, "remix", "tools", "musickit_render_one.py")
    if os.path.isfile(p):
        return p
    return None


class MusickitSource:
    """随机渲染源：状态 + 渲染线程 + 就绪队列。线程安全。"""

    def __init__(self, station=None):
        self.station = station
        self.lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()
        self._started = False
        self.q = queue.Queue(maxsize=max(1, config.MUSICKIT_RENDER_QUEUE_DEPTH))
        self.current = None        # 当前正在播的曲目 meta（{file,title,...}）
        self.channel = config.MUSICKIT_RENDER_CHANNEL
        self.bars = config.MUSICKIT_RENDER_BARS
        self.rendering = False
        self.rendered_count = 0
        self.last_error = ""
        self.last_render_at = 0.0
        self._files = []           # 本模块渲染出的缓存文件（按时间序，用于清理）
        self._prune_cache_disk()   # 跨重启清理：删除历史遗留的旧渲染文件

    # ---------- 生命周期 ----------
    def start(self, channel=None, bars=None):
        """启动渲染线程。已启动则仅更新参数（不重启线程）。"""
        with self.lock:
            if channel:
                self.channel = channel
            if bars:
                self.bars = int(bars)
            # 先置 _started / 清 _stop 再判活：stop() 后立即 start() 时旧线程
            # 可能还在收尾（渲染子进程自然结束），沿用旧线程继续工作，
            # 而不是直接 return 导致源永远不激活。
            self._started = True
            self._stop.clear()
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="musickit-renderer")
            self._thread.start()

    def stop(self):
        """停止渲染并清空就绪队列。"""
        with self.lock:
            self._started = False
            self._stop.set()
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        with self.lock:
            self.current = None

    def set_params(self, channel=None, bars=None):
        with self.lock:
            if channel:
                self.channel = channel
            if bars:
                self.bars = int(bars)

    # ---------- 渲染线程 ----------
    def _run(self):
        while not self._stop.is_set():
            with self.lock:
                channel = self.channel
                bars = self.bars
            self.rendering = True
            meta = self._render_one(channel, bars)
            self.rendering = False
            if meta is None:
                time.sleep(5.0)   # 失败退避，避免热循环
                continue
            with self.lock:
                self.rendered_count += 1
                self.last_render_at = time.time()
                self._files.append(meta["file"])
            try:
                self.q.put(meta, timeout=1.0)
            except queue.Full:
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.q.put_nowait(meta)
                except queue.Full:
                    pass
            self._prune_cache()

    def _render_one(self, channel, bars):
        """子进程渲染一首，返回 meta dict；失败返回 None 并记录 last_error。"""
        script = _renderer_path()
        if not script:
            with self.lock:
                self.last_error = "找不到 musickit_render_one.py（检查 MUSICKIT_ROOT）"
            return None
        cmd = [
            sys.executable,
            script,
            "--channel", channel or "random",
            "--bars", str(bars),
            "--format", config.MUSICKIT_RENDER_FMT,
            "--out", config.MUSICKIT_RENDER_CACHE,
            "--max-tracks", str(config.MUSICKIT_RENDER_MAX_TRACKS),
        ]
        if config.MUSICKIT_RENDER_FUSION:
            cmd.append("--fusion")
        if config.MUSICKIT_RENDER_RELEASE_SAFE:
            cmd.append("--release-safe")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=config.MUSICKIT_RENDER_TIMEOUT,
                cwd=config.MUSICKIT_ROOT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            out = (proc.stdout or "").strip().splitlines()
            if not out:
                raise RuntimeError("渲染器无输出 exit=" + str(proc.returncode))
            data = json.loads(out[-1])
            if not data.get("ok") or not data.get("file") or not os.path.isfile(data["file"]):
                raise RuntimeError(data.get("error") or "渲染器返回无效结果")
            parts = [str(data.get("style") or ""), str(data.get("label") or ""),
                     str(data.get("subgenre") or "")]
            if data.get("bpm"):
                parts.append(str(data["bpm"]) + " BPM")
            title = " · ".join(x for x in parts if x) or os.path.basename(data["file"])
            data["title"] = "随机渲染：" + title
            data["rendered_at"] = time.time()
            with self.lock:
                self.last_error = ""
            return data
        except subprocess.TimeoutExpired:
            with self.lock:
                self.last_error = "渲染超时（>%ss）" % config.MUSICKIT_RENDER_TIMEOUT
        except Exception as e:
            with self.lock:
                self.last_error = type(e).__name__ + ": " + str(e)
        return None

    def _prune_cache_disk(self):
        """跨重启缓存清理：删除渲染缓存目录里超出保留数的最旧文件。

        只清理 MUSICKIT_RENDER_CACHE 目录（本模块专用），按修改时间排序，
        保留最新 MUSICKIT_RENDER_KEEP 个。"""
        try:
            cache = config.MUSICKIT_RENDER_CACHE
            if not os.path.isdir(cache):
                return
            keep = max(1, config.MUSICKIT_RENDER_KEEP)
            files = []
            for name in os.listdir(cache):
                p = os.path.join(cache, name)
                if os.path.isfile(p):
                    try:
                        files.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
            files.sort(reverse=True)   # 新 → 旧
            for _, p in files[keep:]:
                try:
                    os.remove(p)
                except OSError:
                    pass
        except Exception:
            pass

    def _prune_cache(self):
        """删除超出保留数的旧渲染文件（只删本模块产物）。"""
        keep = max(1, config.MUSICKIT_RENDER_KEEP)
        with self.lock:
            files = list(self._files)
        if len(files) <= keep:
            return
        for p in files[:-keep]:
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass
        with self.lock:
            self._files = self._files[len(self._files) - keep:]

    # ---------- 广播者取曲接口 ----------
    def wait_current(self, timeout=1.0):
        """阻塞取下一首。返回 meta；停止时返回 None。"""
        while self._started and not self._stop.is_set():
            try:
                meta = self.q.get(timeout=timeout)
            except queue.Empty:
                continue
            with self.lock:
                self.current = meta
            return meta
        return None

    def advance(self):
        """切下一首：非阻塞取队列里下一首；没有就绪曲目返回 None。"""
        try:
            meta = self.q.get_nowait()
        except queue.Empty:
            return None
        with self.lock:
            self.current = meta
        return meta

    def current_path(self):
        with self.lock:
            return self.current["file"] if self.current else None

    def current_title(self):
        with self.lock:
            return self.current["title"] if self.current else ""

    def status(self):
        with self.lock:
            return {
                "active": self._started,
                "rendering": self.rendering,
                "channel": self.channel,
                "bars": self.bars,
                "queued": self.q.qsize(),
                "rendered_count": self.rendered_count,
                "last_error": self.last_error,
                "cache_dir": config.MUSICKIT_RENDER_CACHE,
                "current": (self.current or {}).get("title", ""),
            }
