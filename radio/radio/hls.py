"""D1 HLS 直播分片：后台 ffmpeg 把 /stream 转成 HLS 切片（含音频 ABR）。

- 后台线程持续跑 ffmpeg：/stream → 多档 AAC-LC → hls/live.m3u8(master) + v_*.m3u8 + seg_*.ts
- 一次解码、多档并行编码（config.HLS_VARIANTS），弱网自动降码率、恢复后自动升回
- 子进程退出（崩溃/源断）自动重启；启动前收掉上一轮遗留的孤儿切片器
- start()/stop()/status() 供 web.py 调用
- 不改现有 ICY /stream，新旧协议并存

对外入口始终是 /hls/live.m3u8：单档时它是媒体播放列表，多档时它是 master 主播放列表，
客户端 URL 无需变更。HLS 让 Safari / iOS / Android 原生 <video> 直接播，移动端体验优于 ICY 长流。
"""
import os
import subprocess
import threading
import time

from . import config

# 项目根目录（radio/ 的上一级）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HLS_DIR = os.path.join(_PROJECT_ROOT, "hls")
# 对外唯一入口。ABR 下它是 master 主播放列表，指向 v_<码率>.m3u8 各档媒体播放列表。
M3U8 = os.path.join(HLS_DIR, "live.m3u8")
# ffmpeg 的 %v 会被替换成 var_stream_map 里的 name=（即 "128k"/"64k"）
_VARIANT_PL_PATTERN = os.path.join(HLS_DIR, "v_%v.m3u8")
_SEGMENT_PATTERN = os.path.join(HLS_DIR, "seg_%v_%05d.ts")
# ffmpeg 的 stderr 落盘位置。必须落盘而不是 PIPE：HLS 是常驻进程，
# PIPE 缓冲区（Windows 约 4–64KB）撑满后 ffmpeg 会阻塞在 write() 上，
# 表现为“进程还在、playlist 却冻结、切片下载 0 字节”的假死。
STDERR_LOG = os.path.join(_PROJECT_ROOT, "hls_ffmpeg.log")

# 进程存活超过这个秒数就认为本轮健康，清掉上一轮遗留的陈旧错误
_HEALTHY_AFTER = 15.0

_lock = threading.Lock()
_proc = None
_thread = None
_stop = False
_restarts = 0
_last_error = ""
_started_at = 0.0


def _ffmpeg_bin():
    """定位 ffmpeg：统一走 config.FFMPEG（与 transcoder 一致，默认 "ffmpeg" 取 PATH）。"""
    return getattr(config, "FFMPEG", "ffmpeg")


def variants():
    """ABR 码率阶梯（kbps，按 master 里的先后顺序；第一档为起播档）。"""
    v = tuple(int(x) for x in getattr(config, "HLS_VARIANTS", (128,)) if int(x) > 0)
    return v or (128,)


def variant_name(kbps):
    """码率 → ffmpeg %v 占位符替换后的名字，也是文件名的一部分。"""
    return f"{int(kbps)}k"


def variant_playlist(kbps):
    """某一档媒体播放列表的绝对路径。"""
    return _VARIANT_PL_PATTERN.replace("%v", variant_name(kbps))


def _cmd():
    port = getattr(config, "PORT", 8000)
    # 源用 /stream/<mount>（per-listener 转码 MP3，保证格式正确）。TRANSCODE_MOUNTS=(64,320)，
    # 取最高码率挂载点保证音质；128 不是挂载点会 404。
    mounts = getattr(config, "TRANSCODE_MOUNTS", (320,))
    br = mounts[-1] if mounts else 320
    bin_ = _ffmpeg_bin()
    vs = variants()
    seg_sec = getattr(config, "HLS_SEGMENT_SEC", 2)
    list_size = getattr(config, "HLS_LIST_SIZE", 8)
    del_thresh = getattr(config, "HLS_DELETE_THRESHOLD", 4)

    # 源用 per-listener 转码流而非共享广播者 /stream（中途加入首字节非文件头，ffmpeg 探测失败）。
    # HLS 只有一个 ffmpeg 进程，per-listener 开销可接受；主 /stream 多听众仍走广播者共享。
    cmd = [
        bin_, "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
        # --- 输入侧：低延迟 + 断流自动重连 ---
        "-fflags", "nobuffer", "-flags", "low_delay",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
        "-i", f"http://localhost:{port}/stream/{br}",
        "-vn",                        # 丢弃 APIC 封面图（被当成视频流会阻塞 HLS 切片）
    ]
    # --- ABR：同一路输入 map 成 N 路输出，一次解码 / 多档编码，比跑 N 个进程省一半 CPU ---
    for _ in vs:
        cmd += ["-map", "0:a"]
    # -c:a aac 即 AAC-LC，HLS 兼容性最好（Safari/iOS/Android 原生支持，勿换 HE-AAC）
    cmd += ["-c:a", "aac", "-ac", "2", "-ar", "44100"]
    for i, kbps in enumerate(vs):
        cmd += [f"-b:a:{i}", f"{kbps}k"]
    cmd += ["-flush_packets", "1"]    # 每包即刻落盘，别攒在 muxer 里

    # --- 输出侧：短切片压低端到端延迟（6s→2s 约把延迟从 ~20s 压到 ~6-8s）---
    cmd += [
        "-f", "hls",
        "-hls_time", str(seg_sec),
        "-hls_list_size", str(list_size),
        "-hls_delete_threshold", str(del_thresh),
        "-hls_segment_type", "mpegts",
        # independent_segments：每片可独立解码，播放器可从任意片起播（ABR 切档的前提）
        # program_date_time：写 EXT-X-PROGRAM-DATE-TIME，便于对时/跳转
        # temp_file：切片先写 .tmp 再原子改名，杜绝播放器抓到半截 .ts
        # 不用 append_list：每轮启动都会清空 hls 目录，它没有续接对象，
        # 反而会在序号 0 处凭空写出一个 EXT-X-DISCONTINUITY
        "-hls_flags",
        "delete_segments+omit_endlist+independent_segments"
        "+program_date_time+temp_file",
        # var_stream_map 决定 master 里的档位顺序；name: 的值会替换输出路径里的 %v
        # 注意分隔符是冒号（name:128k），写成 name=128k 会报 "Invalid keyval"
        "-var_stream_map",
        " ".join(f"a:{i},name:{variant_name(k)}" for i, k in enumerate(vs)),
        # master 落在输出 playlist 所在目录，文件名沿用 live.m3u8 → 对外 URL 不变
        "-master_pl_name", os.path.basename(M3U8),
        "-hls_segment_filename", _SEGMENT_PATTERN,
        _VARIANT_PL_PATTERN,
    ]
    return cmd


def reap_orphans():
    """收掉上一轮遗留的切片器进程。

    服务进程被强杀（taskkill /F、崩溃、断电重来）时，ffmpeg 子进程会成为孤儿
    继续往同一个 hls 目录写，和新切片器抢同一份 playlist —— 表现为序列号乱跳、
    切片刚出现就被对方删掉、客户端 404。所以启动前必须先收尸。

    按“命令行里含本项目 hls 输出目录”精确匹配（不能匹配 live.m3u8：ABR 下命令行里
    只有 v_%v.m3u8 模板和 -master_pl_name 的裸文件名）。不用 PID 文件，避免 PID 复用
    误杀到转码用的 ffmpeg。末尾带路径分隔符，防止误伤 hls_ffmpeg.log 之类的同前缀路径。
    """
    needle = HLS_DIR.rstrip("\\/") + os.sep
    try:
        if os.name == "nt":
            # PowerShell 单引号字符串里反斜杠是字面量，-like 只认 * 和 ?，直接拼路径即可
            ps = (
                "Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" | "
                "Where-Object { $_.CommandLine -like '*" + needle.replace("'", "''") + "*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, timeout=20,
            )
        else:
            subprocess.run(["pkill", "-f", needle], capture_output=True, timeout=10)
    except Exception:
        pass


def _tail_stderr(limit=400):
    """读 ffmpeg stderr 日志的最后一行有效内容（诊断用）。"""
    try:
        with open(STDERR_LOG, "rb") as f:
            try:
                f.seek(-8192, os.SEEK_END)
            except OSError:
                f.seek(0)
            txt = f.read().decode("utf-8", "replace").strip()
        return txt.splitlines()[-1][:limit] if txt else ""
    except OSError:
        return ""


def _runner():
    global _proc, _restarts, _last_error, _started_at
    while not _stop:
        errf = None
        try:
            os.makedirs(HLS_DIR, exist_ok=True)
            # 清理旧切片，避免重启后残留段污染 playlist
            for fn in os.listdir(HLS_DIR):
                if fn.endswith((".ts", ".m3u8", ".tmp")):
                    try:
                        os.remove(os.path.join(HLS_DIR, fn))
                    except OSError:
                        pass
            # stderr 重定向到文件而非 PIPE：常驻进程用 PIPE 会因缓冲区写满而死锁
            errf = open(STDERR_LOG, "wb")
            _proc = subprocess.Popen(
                _cmd(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=errf,
            )
            _started_at = time.time()
            # 轮询代替阻塞 wait()：既能及时响应 stop()，又能在进程稳定后清掉陈旧错误
            cleared = False
            while True:
                rc = _proc.poll()
                if rc is not None:
                    break
                if _stop:
                    return
                if not cleared and time.time() - _started_at > _HEALTHY_AFTER:
                    _last_error = ""      # 本轮已稳定，上一轮的错误不再有参考价值
                    cleared = True
                time.sleep(0.5)
            if _stop:
                break
            _restarts += 1
            err = _tail_stderr()
            _last_error = err or f"exit code {rc}"
        except FileNotFoundError:
            _last_error = f"ffmpeg 未找到：{_ffmpeg_bin()}"
            break   # 没装 ffmpeg，重启无意义
        except Exception as e:
            _last_error = str(e)
        finally:
            if errf:
                try:
                    errf.close()
                except OSError:
                    pass
        _proc = None
        _started_at = 0.0
        if not _stop:
            time.sleep(2)   # 崩溃后 2s 重启


def start():
    """启动 HLS 切片后台线程（幂等，重复调用安全）。"""
    global _thread, _stop
    with _lock:
        if _thread and _thread.is_alive():
            return False
        reap_orphans()      # 先清掉上一轮强杀留下的孤儿 ffmpeg，否则两个切片器互相打架
        _stop = False
        _thread = threading.Thread(target=_runner, daemon=True, name="hls-slicer")
        _thread.start()
        return True


def stop():
    """停止切片，清理子进程。"""
    global _stop, _proc
    with _lock:
        _stop = True
        if _proc and _proc.poll() is None:
            try:
                _proc.terminate()
                _proc.wait(timeout=3)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
        _proc = None


def status():
    """返回切片器状态（供 /api/hls/status）。"""
    running = _proc is not None and _proc.poll() is None
    # 统计当前切片数与 m3u8 大小
    seg_count = 0
    m3u8_size = 0
    files = []
    try:
        if os.path.isdir(HLS_DIR):
            files = os.listdir(HLS_DIR)
            seg_count = sum(1 for f in files if f.endswith(".ts"))
            m3u8_size = os.path.getsize(M3U8) if os.path.isfile(M3U8) else 0
    except OSError:
        pass
    # 每档 ABR 的就绪情况：master 有了不代表各档都在出片
    vinfo = []
    for kbps in variants():
        nm = variant_name(kbps)
        vinfo.append({
            "bitrate": kbps,
            "name": nm,
            "playlist": f"/hls/{os.path.basename(variant_playlist(kbps))}",
            "ready": os.path.isfile(variant_playlist(kbps)),
            "segments": sum(1 for f in files if f.startswith(f"seg_{nm}_") and f.endswith(".ts")),
        })
    return {
        "running": running,
        "uptime_sec": round(time.time() - _started_at, 1) if running and _started_at else 0,
        "restarts": _restarts,
        "m3u8_exists": os.path.isfile(M3U8),
        "m3u8_size": m3u8_size,
        "m3u8_mtime": round(os.path.getmtime(M3U8), 1) if os.path.isfile(M3U8) else 0,
        "segment_count": seg_count,
        "abr": len(vinfo) > 1,
        "variants": vinfo,
        "last_error": _last_error,
        "ffmpeg": _ffmpeg_bin(),
        "dir": HLS_DIR,
        "stderr_log": STDERR_LOG,
    }
