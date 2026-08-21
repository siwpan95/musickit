"""启动入口：优先用 waitress 提供多听众并发，否则退回 Flask 开发服务器。

用法：
    python run.py              # 只起本地服务
    python run.py --expose     # 起服务 + 自动 cloudflared quick tunnel（公网收听）
    python run.py --expose ngrok   # 同上但用 ngrok（failover 备选）

高级穿透（named tunnel 自定义域名 / 多隧道 failover）仍用：
    bash expose.sh [quick|named <域名>|ngrok]

--expose 自带守护：持续解析公网地址、验证可达后写回面板、
隧道进程意外退出自动重新拉起（quick 模式地址每次可能变化）。
"""
import os
import re
import sys
import time
import atexit
import shutil
import subprocess
import threading

# 优先使用项目自带的依赖包（本地便携），其次用系统全局包
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_PROJECT_DIR, "packages"))
sys.path.insert(0, _PROJECT_DIR)

from radio import config
from radio.web import app, station

PUBLIC_URL_FILE = os.path.join(_PROJECT_DIR, "public_url.txt")
# 穿透二进制目录：项目自带（与 ffmpeg/ 同策略），换盘符/搬目录都不会失效
CF_DIR = os.path.join(_PROJECT_DIR, "cloudflared")


def _find_cloudflared():
    """定位 cloudflared 二进制：项目自带的 cloudflared/ 优先，PATH 兜底。"""
    cand = os.path.join(CF_DIR, "cloudflared-windows-amd64.exe")
    if os.path.isfile(cand):
        return cand
    return shutil.which("cloudflared")


def _find_ngrok():
    """定位 ngrok 二进制。"""
    for cand in (os.path.join(CF_DIR, "ngrok-v3-stable-windows-amd64", "ngrok.exe"),
                 shutil.which("ngrok")):
        if cand and os.path.isfile(cand):
            return cand
    return None


def _write_public_url(url):
    """把公网地址写回 public_url.txt（面板轮询显示）。"""
    try:
        with open(PUBLIC_URL_FILE, "w", encoding="utf-8") as f:
            f.write((url or "") + "\n")
    except Exception:
        pass


def _verify_public_url(url, tries=5, interval=2):
    """验证公网地址真实可用（隧道域名刚注册时边缘可能尚未就绪，会短暂 502）。

    返回 (ok, note)：ok=True 表示本机可直接访问；
    note 说明失败原因：'dns'（本机解析不了域名，常见于运营商 DNS 污染/负缓存）
    或 'unreachable'（域名可解析但暂不可达）。
    """
    import socket
    from urllib import request as ur
    target = url.rstrip("/") + "/api/status"
    dns_fail = False
    for _ in range(tries):
        try:
            with ur.urlopen(target, timeout=8) as r:
                if r.status == 200 and r.read(64):
                    return True, ""
        except Exception as e:
            if isinstance(getattr(e, "reason", None), socket.gaierror):
                dns_fail = True
        time.sleep(interval)
    if dns_fail:
        return False, "dns"
    return False, "unreachable"


def _verify_public_url_doh(url, tries=2, interval=2):
    """绕过本机 DNS 验证隧道真实可用性：DoH 公共解析 + 直连边缘 IP（SNI/Host 指定原域名）。

    用于区分两种失败：隧道本身没起来（边缘 502/无记录） vs 本机运营商 DNS
    污染/负缓存（域名实际存在，公共 DNS 能解析、隧道能服务）。
    """
    import json
    import socket
    import ssl
    import urllib.parse
    from urllib import request as ur
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if not host:
        return False
    path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
    doh_servers = (
        "https://dns.alidns.com/resolve",
        "https://doh.pub/dns-query",
        "https://1.1.1.1/dns-query",
    )
    ips = []
    for _ in range(tries):
        for doh in doh_servers:
            try:
                q = doh + "?name=" + urllib.parse.quote(host) + "&type=A"
                req = ur.Request(q, headers={"Accept": "application/dns-json"})
                with ur.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                ips = [a.get("data") for a in data.get("Answer", [])
                       if a.get("type") == 1 and a.get("data")]
                if ips:
                    break
            except Exception:
                continue
        if ips:
            break
        time.sleep(interval)
    if not ips:
        return False
    for ip in ips:
        try:
            ctx = ssl.create_default_context()
            ctx.set_alpn_protocols(["http/1.1"])
            with socket.create_connection((ip, 443), timeout=8) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    req_line = ("GET " + path + " HTTP/1.1\r\n"
                                "Host: " + host + "\r\n"
                                "User-Agent: radio-verify\r\n"
                                "Connection: close\r\n\r\n")
                    ssock.sendall(req_line.encode())
                    buf = b""
                    while b"\r\n\r\n" not in buf and len(buf) < 16384:
                        chunk = ssock.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                    first_line = buf.split(b"\r\n", 1)[0].decode("latin-1", "replace")
                    return first_line.startswith("HTTP/1.1 200")
        except Exception:
            continue
    return False


def start_tunnel(port, mode="quick"):
    """启动穿透子进程 + 守护线程，写回公网地址，注册 atexit 清理。

    mode: 'quick'(cloudflared trycloudflare) | 'ngrok'
    守护行为（针对"公网穿透拉不起来/失效"）：
      - 不再只等 30s：只要进程活着就持续解析，地址晚到也能自动显示；
      - 拿到地址先验证真实可达，再写 public_url.txt（面板不会显示死链）；
      - 隧道进程意外退出自动重新拉起并重新获取地址（trycloudflare 域名每次都变）。
    返回 holder（dict，含当前进程引用，供 atexit 清理）。"""
    holder = {"proc": None}
    _stop = threading.Event()

    def _cleanup():
        p = holder.get("proc")
        if p and p.poll() is None:
            try:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except Exception:
                    p.kill()
            except Exception:
                pass
        if os.path.exists(PUBLIC_URL_FILE):
            try:
                os.remove(PUBLIC_URL_FILE)
            except OSError:
                pass
    atexit.register(_cleanup)

    if mode == "ngrok":
        bin_ = _find_ngrok()
        if not bin_:
            print("   [!] 未找到 ngrok，改用 cloudflared quick tunnel")
            return start_tunnel(port, "quick")
        log_file = os.path.join(_PROJECT_DIR, "ngrok.log")

        def _spawn_ngrok():
            return subprocess.Popen(
                [bin_, "http", str(port), "--log=stdout"],
                stdout=open(log_file, "w"), stderr=subprocess.STDOUT,
            )

        def _watch_ngrok():
            import json as _json
            import urllib.request
            proc = _spawn_ngrok()
            holder["proc"] = proc
            got = False
            warned_auth = False
            while not _stop.is_set():
                if proc.poll() is not None:
                    if got:
                        print("   [!] ngrok 进程退出，尝试重新拉起…", flush=True)
                        got = False
                    time.sleep(3)
                    proc = _spawn_ngrok()
                    holder["proc"] = proc
                    continue
                try:
                    r = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2)
                    data = _json.loads(r.read())
                    for t in data.get("tunnels", []):
                        u = t.get("public_url", "")
                        if u.startswith("http") and not got:
                            ok, note = _verify_public_url(u)
                            _write_public_url(u)   # 地址来自 ngrok API，权威可信；先展示
                            print(f"   🌐 公网地址：{u}/stream  （面板自动显示）", flush=True)
                            if not ok:
                                doh_ok = _verify_public_url_doh(u)
                                if note == "dns" and doh_ok:
                                    print("   [!] 隧道已通过公共 DNS 验证可用；本机运营商 DNS 解析异常，"
                                          "可 ipconfig /flushdns 或换公共 DNS（1.1.1.1 / 223.5.5.5）", flush=True)
                                elif note == "dns":
                                    print("   [!] 本机暂时解析不了该域名（运营商 DNS 常见）；"
                                          "听众若打不开可换公共 DNS（1.1.1.1 / 223.5.5.5）", flush=True)
                                else:
                                    print("   [!] 隧道刚建立，边缘尚未就绪，稍后自动生效", flush=True)
                            got = True
                        break
                except Exception:
                    pass
                if not got and not warned_auth:
                    try:
                        with open(log_file, encoding="utf-8", errors="replace") as f:
                            tail = f.read()
                        if "authtoken" in tail or "not authenticated" in tail:
                            warned_auth = True
                            print("   [!] ngrok 需要账号凭据：先执行 ngrok config add-authtoken <令牌>",
                                  flush=True)
                    except Exception:
                        pass
                time.sleep(2)
        threading.Thread(target=_watch_ngrok, daemon=True).start()
        return holder

    # quick：cloudflared trycloudflare
    bin_ = _find_cloudflared()
    if not bin_:
        print(f"   [!] 未找到 cloudflared（{CF_DIR}/ 或 PATH），跳过穿透", flush=True)
        print("       高级用法：bash expose.sh named <域名>  或  bash expose.sh ngrok", flush=True)
        return None
    log_file = os.path.join(_PROJECT_DIR, "cloudflared.log")

    def _spawn_cf():
        return subprocess.Popen(
            [bin_, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
            stdout=open(log_file, "w"), stderr=subprocess.STDOUT,
        )

    def _watch_cf():
        pat = re.compile(r"https://[a-z0-9.-]*\.trycloudflare\.com")
        proc = _spawn_cf()
        holder["proc"] = proc
        got = False
        warned = False
        dns_recycles = 0
        last_url = ""
        pending = ""          # 已展示但未验证通过的地址（持续后台补验）
        pending_tries = 0
        while not _stop.is_set():
            if proc.poll() is not None:
                if got:
                    print("   [!] 隧道进程退出，重新拉起并获取新地址…", flush=True)
                    got = False
                    pending = ""
                else:
                    print("   [!] cloudflared 未成功启动，3 秒后重试…", flush=True)
                time.sleep(3)
                proc = _spawn_cf()
                holder["proc"] = proc
                last_url = ""
                continue
            try:
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                content = ""
            if not got:
                urls = pat.findall(content)
                u = urls[-1] if urls else ""
                if u:
                    ok, note = _verify_public_url(u)
                    if ok:
                        _write_public_url(u)
                        print(f"   🌐 公网地址：{u}/stream  （面板自动显示）", flush=True)
                        got = True
                    elif note == "dns" and dns_recycles < 6 and u != last_url:
                        # 本机解析不了这个随机域名（运营商 DNS 污染/负缓存常见）：
                        # 换一个隧道域名再试 —— trycloudflare 每次注册域名都随机。
                        dns_recycles += 1
                        last_url = u
                        print(f"   [!] 本机 DNS 解析不了 {u.split('//')[1]}（运营商 DNS 问题），"
                              f"换一个隧道域名重试（{dns_recycles}/6）…", flush=True)
                        try:
                            proc.terminate()
                            try:
                                proc.wait(timeout=3)
                            except Exception:
                                proc.kill()
                        except Exception:
                            pass
                        proc = _spawn_cf()
                        holder["proc"] = proc
                        time.sleep(5)
                    else:
                        # 边缘未就绪 / 回收次数用尽：地址来自 cloudflared 日志，权威可信，
                        # 先展示并附提示，绝不因本机验证失败而隐藏地址；之后后台持续补验。
                        _write_public_url(u)
                        print(f"   🌐 公网地址：{u}/stream  （面板自动显示）", flush=True)
                        if note == "dns":
                            print("   [!] 本机暂时解析不了该域名（运营商 DNS 常见）；"
                                  "正在后台验证隧道可用性…", flush=True)
                        else:
                            print("   [!] 隧道刚建立，边缘尚未就绪；正在后台验证隧道可用性…", flush=True)
                        pending = u
                        pending_tries = 0
                        got = True
                elif not warned and "control stream encountered a failure" in content:
                    warned = True
                    print("   [!] Cloudflare 快速隧道暂时连接失败（服务端波动），"
                          "正在持续重试，地址拿到后会自动显示…", flush=True)
            elif pending:
                # 后台补验：地址已展示，继续验证直到通过（上限约 2 分钟）
                pending_tries += 1
                if pending_tries <= 15:
                    if _verify_public_url_doh(pending, tries=1, interval=1):
                        print("   ✓ 隧道已验证可用（公共 DNS 直连 200）；"
                              "本机若仍打不开可 ipconfig /flushdns 或换公共 DNS（1.1.1.1 / 223.5.5.5）",
                              flush=True)
                        pending = ""
                else:
                    pending = ""
            time.sleep(2)
        if holder.get("proc") and holder["proc"].poll() is None:
            try:
                holder["proc"].terminate()
            except Exception:
                pass

    threading.Thread(target=_watch_cf, daemon=True).start()
    return holder


def main():
    # 解析 --expose 选项
    args = sys.argv[1:]
    # 控制台编码兜底：GBK 终端（默认 cmd / 双击 .bat）打印 emoji 会 UnicodeEncodeError，
    # 统一转成 UTF-8 输出，任何代码页都能正常启动。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

    expose = "--expose" in args
    expose_mode = "quick"
    if expose:
        i = args.index("--expose")
        if i + 1 < len(args) and args[i + 1] in ("quick", "ngrok"):
            expose_mode = args[i + 1]

    print(f"\n📻 {config.STATION_NAME} 启动中…")
    print(f"   控制面板 : http://localhost:{config.HTTP_PORT}/")
    print(f"   收听地址 : http://localhost:{config.HTTP_PORT}/stream")
    print(f"   歌曲目录 : {config.MUSIC_DIR}  （{station.status()['playlist_size']} 首）")
    if expose:
        print(f"   穿透模式 : {expose_mode}（公网收听自动开启）")
    print("   按 Ctrl+C 停止\n")

    if expose:
        start_tunnel(config.HTTP_PORT, expose_mode)

    try:
        try:
            from waitress import serve
            serve(
                app,
                host=config.HOST,
                port=config.HTTP_PORT,
                threads=8,
                channel_timeout=60,
            )
        except ImportError:
            print("（未安装 waitress，使用 Flask 开发服务器；"
                  "生产环境建议：pip install waitress）\n")
            app.run(host=config.HOST, port=config.HTTP_PORT, threaded=True)
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
