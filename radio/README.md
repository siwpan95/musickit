# 📻 我的Python电台

一个用 **纯 Python + Flask** 搭建的轻量级网络电台。把本地歌曲（或 musickit
随机渲染的混音）变成一条 24/7 的音频流，任何设备（手机 / 电脑 / 播放器）都能收听，
还能在网页上实时控制播放、看 “正在播放”。

> 转播（relay）功能已于 2026-08-23 剥离并移交 Node.js 版
> （D:\private-radio-stations-2.0，gitee siwpan/private-radio-stations 分支 3.0）；
> 全套存档见该仓库 archived 分支的 python-radio-relay-20260823/。

> 设计取舍：相比 Icecast + libshout 或 Cycast（需要 Cython 编译 / 独立服务），
> 本方案**零外部服务、纯 Python 即可运行**，一个人也能轻松维护和二次开发。
> 代价是并发能力靠 WSGI 服务器（waitress）支撑，适合个人 / 小圈子电台。

---

## ✨ 功能

- 🎵 **本地歌单流**：自动扫描 `music/` 目录，循环播放（支持 mp3/ogg/flac/wav）
- 🎲 **musickit 随机渲染源（F 层）**：默认音源。由 `G:\music\musickit` 引擎实时渲染随机混音
  （随机混音师签名 × 随机流派提示词 × 随机 stems）代替本地 music/ 歌单，
  渲染好的 MP3 经广播者照常推流（ICY/HLS/多码率/录音全兼容）
- 🏷️ **ICY 元数据**：播放器（VLC / Winamp / PotPlayer）能显示 “正在播放”
- 🎛️ **Premium 控制面板**：玻璃拟态 + vaporwave 渐变 + 合成波网格 + 辉光微交互（明暗主题）
- 💿 **实时可视化**：音频驱动的中心旋转唱片 + 放射状频谱（Web Audio `AnalyserNode`）
- 🌗 **明暗主题**：控制面板跟随系统并记忆偏好
- ⚡ **节奏自适应**：按文件比特率（MP3 帧头嗅探）控制推流速度，客户端不卡顿
- 🔁 **转码固定 MP3（B1）**：挂载点/录音统一经 ffmpeg 转成固定码率 MP3，浏览器 / 老客户端都能播
- 🎚️ **多码率挂载点（B3）**：`/stream/64`、`/stream/320` 额外挂载点，手机省流量 / WiFi 高音质
- 📺 **HLS 直播切片（D1）**：自动把广播切成 HLS，Safari / iOS / Android 原生播放器直接打开 `http://localhost:8000/hls/live.m3u8` 即可收听（无需 VLC/插件）；支持**音频 ABR 多码率自适应**（默认 128k / 64k 两档，播放器按网速自动切换），AAC-LC 编码原生兼容
- 🔔 **开场台标音（B4）**：新听众连入先放一段 jingle，可替换 `jingle.mp3`（文件不存在则跳过）
- 🔴 **边播边录（B2）**：一键把当前广播录成干净 MP3 存到 `recordings/`（可做回听）；录音时主串流自动切固定 MP3 以保证录制文件干净
- 🏷️ **本地标签 + 内嵌封面（C1）**：自动读取 ID3/FLAC/M4A/OGG 的标题/歌手/专辑，抽出 APIC 内嵌封面显示在「正在播放」（纯 mutagen，离线）
- 📱 **PWA 可安装（C4）**：`manifest.webmanifest` + service worker + 图标，可「添加到主屏幕」当 App 用，离线也能打开壳
- 🎙️ **播客 RSS（C5）**：`/rss` 把 `recordings/` 里的录音作为播客订阅源发出去，播客 App 可订阅回听
- 🎤 **歌词显示（C2）**：本地同名 `.lrc` 优先（离线），缺失时走 LRCLIB 在线查询（零密钥）；面板里按播放进度同步高亮滚动
- 🔗 **社群同步（C3）**：当前曲一键发布到 Discord webhook / Telegram 频道；凭据存 `integrations.json`，GET 接口只返回布尔状态不泄露密钥

---

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
# musickit 随机渲染源还需引擎依赖（已随 musickit 环境安装）：
#   pydub numpy scipy soundfile audioop-lts

# 2. 音源二选一（默认 musickit 随机渲染，无需放歌）：
#    a. musickit 随机渲染：由 musickit 引擎实时渲染随机混音（见下方 F 层），默认开启
#    b. 传统歌单：把歌曲丢进 music/ 目录（mp3/ogg/flac/wav），面板里切回歌单模式

# 3. 启动（项目已并入 G:\music\musickit，电台位于 radio/ 子目录）
python G:\music\musickit\radio\run.py                # 只起本地服务
python G:\music\musickit\radio\run.py --expose       # 起服务 + 自动 cloudflared 公网穿透（trycloudflare 临时域名）
python G:\music\musickit\radio\run.py --expose ngrok # 同上但用 ngrok（需先配置 authtoken）
python G:\music\musickit\radio\run.py --expose lhr   # 同上但用 localhost.run（免账号 SSH 隧道，部分网络不可用）
```

打开浏览器：

- 控制面板：<http://localhost:8000/>
- 直接收听：<http://localhost:8000/stream>（VLC 打开这个地址）
- HLS 原生收听：<http://localhost:8000/hls/live.m3u8>（Safari / iPhone / Android 播放在线广播 App 直接打开，支持多码率自适应）

> `--expose` 会自动启动 cloudflared quick tunnel，公网地址写回面板（面板自动显示可复制分享）。
> 穿透带守护：持续解析地址（不再 30 秒放弃）、验证可用后才标注 ✓、隧道进程意外退出自动重新拉起并重新获取地址；
> 若本机运营商 DNS 解析不了 trycloudflare 随机域名（常见污染/负缓存），会自动换域名重试并在后台补验，
> 提示可 `ipconfig /flushdns` 或换公共 DNS（1.1.1.1 / 223.5.5.5）。
> `--expose ngrok` 需先配置 authtoken（注册若被谷歌 reCAPTCHA 拦下，可用 **GitHub 账号登录 ngrok** 绕过：
> 先在 github.com 免费注册，再到 ngrok 登录页点 "Continue with GitHub"，登录后到
> dashboard.ngrok.com/get-started/your-authtoken 复制令牌，执行
> `ngrok config add-authtoken <令牌>`）。
> ngrok 免费版注意：浏览器首次访问会显示 ngrok 中转确认页（点 Visit Site 即可，播放器/curl 不受影响）；
> 可在 dashboard 免费领取 1 个静态域名并执行
> `setx NGROK_STATIC_DOMAIN "你的域名.ngrok-free.dev"`（或直接填 `radio/config.py`），
> 之后 `--expose ngrok` 的公网地址固定不变（新开的终端生效）。
> `--expose lhr` 走 localhost.run 免账号 SSH 隧道（Windows 自带 OpenSSH），注意部分网络（含国内运营商）
> 到其 AWS 边缘的数据面不通，只作备用。
> Ctrl+C 停止时自动清理穿透子进程。高级用法（named tunnel 自定义域名 / 多隧道 failover）仍用 `bash expose.sh`。
> 没装 `waitress` 也能跑，会退回 Flask 开发服务器；多听众并发建议装上。

---

## 🧩 项目结构

```
radio/
  __init__.py     包说明
  config.py       全局配置（端口 / 台名 / 比特率 / 功能开关）
  mp3info.py      MP3 帧头比特率嗅探（纯 Python）
  station.py      电台状态机：歌单管理 + 播放控制（线程安全）
  streamer.py     流生成器：歌单流（歌单/musickit 渲染件）+ ICY 元数据 + 多码率 / 录音
  hls.py          HLS 直播切片（D1）：ABR 主/变播放列表生成 + ffmpeg 调用
  transcoder.py   ffmpeg 转码基础设施（B 层：转码 / 挂载点 / jingle / 录音）
  metadata.py     本地标签 + 内嵌封面读取（C1，纯 mutagen）
  lyrics.py       歌词双源：本地 LRC + LRCLIB 在线（C2，零密钥）
  integrations.py Discord/Telegram 社群同步（C3，后台线程发布）
  musickit_source.py  musickit 随机渲染源（F 层）：后台预渲染队列 + 广播者接入
  pwa/            PWA 资源：manifest.webmanifest / sw.js / icon-*.png（C4）
  web.py          Flask 路由：控制面板 + 流媒体接口 + C 层 API
  templates/
    index.html    Premium 控制面板 UI
run.py            启动入口（waitress / Flask 自动降级）
requirements.txt  依赖
music/            歌曲目录（传统歌单模式用；默认已由 musickit 随机渲染代替）
render_cache/     musickit 随机渲染缓存（F 层，自动创建/清理，保留最近 20 首）
integrations.json 社群同步凭据（C3：discord_webhook / telegram_token / telegram_chat_id / enabled）
expose.sh         外网穿透一键脚本（自动确认服务 + 选 ngrok / cloudflared，并把公网地址回写面板）
jingle.mp3        开场台标音（占位音，可替换成你自己的；文件删除则跳过）
recordings/       录音输出目录（B2 边播边录；C5 播客 RSS 源）
ffmpeg/          项目自带 ffmpeg 7.1 + ffprobe（转码 / 切片依赖，不依赖全局 PATH）
hls/             HLS 切片输出目录（live.m3u8 主播放列表 + v_128k/v_64k 变播放列表 + seg_*.ts）
hls_ffmpeg.log   ffmpeg 切片进程 stderr（排查切片问题）
```

> 整合前的零散尝试（`1.py` Icecast+libshout 推流 · `2.py` FFmpeg 推流 · `3/8.py` 控制 API ·
> `4/5.py` Flask 歌单流 · `6.py` 麦克风直播 · `7.py` ICY 头 · `9.txt` 本地+网络电台调研）
> 已于 2026-08-23 移入统一归档区（gitee siwpan/private-radio-stations 的 archived 分支，
> `python-radio-experiments/`）。

---

## 🔌 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/`              | 控制面板网页 |
| GET  | `/stream`        | 音频流（支持 `Icy-MetaData: 1` 元数据）|
| GET  | `/api/status`    | 当前状态 JSON |
| POST | `/api/next`      | 下一首 |
| POST | `/api/pause`     | 暂停 / 继续 |
| POST | `/api/shuffle`   | 切换随机播放 |
| POST | `/api/rescan`    | 重新扫描歌单 |
| GET  | `/stream/<k>`    | 多码率挂载点，`k` ∈ {64, 320}（转码到该码率 MP3）|
| POST | `/api/record`    | 录音开关 `{"action":"start"｜"stop"}`（开启后广播录成 MP3）|
| GET  | `/api/meta`      | 当前/指定本地曲目标签 `?path=`（C1，title/artist/album）|
| GET  | `/api/cover`     | 当前/指定本地曲目内嵌封面图片 `?path=`（C1，无则 404）|
| GET  | `/api/lyrics`    | 歌词 `?path=`（C2，本地 LRC 优先 → LRCLIB 在线；返回 lines/plain/source/synced）|
| GET/POST | `/api/integrations` | 社群同步配置（C3，GET 只返回布尔启用状态，POST 写 integrations.json）|
| POST | `/api/announce`  | 立即把当前曲发布到 Discord/Telegram（C3，无凭据不报错）|
| GET  | `/rss`           | 播客 RSS 2.0（C5，基于 recordings/*.mp3）|
| GET  | `/recordings/<name>` | 录音文件下载（C5，防目录穿越）|
| GET  | `/manifest.webmanifest` `/sw.js` `/icon-*.png` | PWA 资源（C4）|
| GET  | `/hls/live.m3u8` | HLS **ABR 主播放列表**（指向各码率变播放列表，播放器原生自适应切换）|
| GET  | `/hls/v_128k.m3u8` · `/hls/v_64k.m3u8` | 各码率变播放列表（AAC-LC：128k 起播 / 64k 弱网）|
| GET  | `/api/hls/status` | HLS 切片器状态（运行中 / 各码率就绪 / 最后错误）|
| GET  | `/api/health`     | 健康检查：模式 / 听众数 / uptime / 磁盘 / HLS / 隧道 / subscribers |
| GET  | `/api/public-url` | 当前公网地址（隧道打通后由 run.py 写回，面板自动显示）|

---

## 📺 HLS 直播（Safari / iOS / Android 原生）

除了传统的 `/stream`（需 VLC / 支持 ICY 的播放器），电台还会**自动切片成 HLS**，
让 iPhone、iPad、Mac Safari、Android 播放在线广播的 App **直接打开就能听**，无需任何插件。

- **主播放列表（ABR 自适应）**：`/hls/live.m3u8`
  - 内部声明两档码率：`v_128k.m3u8`（128 kbps，起播 / 高音质）、`v_64k.m3u8`（64 kbps，弱网省流量）
  - 播放器按实时网速在码率间自动切换，网络恢复后也会回升
- **编码**：AAC-LC（`-c:a aac`，44.1 kHz / 双声道）—— Safari / iOS / Android 原生支持
- **低延迟**：切片 2 s + 滚动窗口 8 片 ≈ 16 s 直播延迟（远低于传统 HLS 的 30–60 s）
- **缓存策略（已内置正确响应头，无需操心）**：
  - `.m3u8` 播放列表 `no-store`（否则被 CDN / 浏览器缓存后直播“卡住不动”）
  - `.ts` 切片 `immutable` 长缓存（切片名唯一、内容不变，省带宽）
  - 全开 CORS，可把公网地址嵌到任意网页 / 第三方播放器

> 切片由 ffmpeg 后台线程完成（命令 stderr 落 `hls_ffmpeg.log`）。ffmpeg 是**项目自带 7.1 版**
> （`ffmpeg/ffmpeg.exe`，随项目走、不依赖全局 PATH 上可能过旧的版本）。
> 找不到 ffmpeg 时 HLS 切片会安全跳过，主服务与其它功能不受影响。

状态查看：`GET /api/hls/status`（运行中 / 各码率是否就绪 / 最后错误）。

---

## 🌍 让外网也能收听

默认只在局域网。要让互联网上的人也能听，二选一（Python 程序不用改）：

1. **有公网 IP**：路由器端口转发 `8000 -> 8000`，听众用
   `http://你的公网IP:8000/stream`。
2. **无公网 IP**：用内网穿透，一行命令搞定：
   ```bash
   ngrok http 8000          # 生成公网 URL
   # 或 Cloudflare Tunnel（更稳定、可自定义域名）
   ```
3. **一键脚本**：`bash expose.sh` 自动确认电台服务在跑（没跑就启动），再自动选 `ngrok` / `cloudflared` 打通外网；两者都没装会给出安装指引。打通后把公网地址的 `/stream` 发给朋友即可收听。

需要更专业的能力（多频道、自动 DJ、节目单）可后续接入 Icecast / LiquidSoap。

---

## 🧩 浏览器扩展

原 `extension/`（转播控制为核心的 MV3 扩展）已随转播功能剥离归档；
替代品见 Node.js 版项目（`D:\private-radio-stations-2.0\extension`，对齐其 3.0 API）。

---

## 🛠️ 已知限制 / 后续可优化

- 每个听众独立读取音频文件（非共享广播缓冲），人数多时磁盘 IO 略高；
  可加一个共享环形缓冲升级为“真广播”。
- 暂停是“挂起连接”，客户端缓冲耗尽后会自然停；恢复了接着播。
- 麦克风直播源（`live.py` 思路，见归档区 python-radio-experiments/6.py）需要本机 ffmpeg，默认未启用。
- HLS 自适应在**切片边界**才切换码率，弱网时最多滞后一个切片（2 s）才降档；quick-tunnel 刚启动可能有几秒 `530`（“origin not ready” 暖机），重试即恢复。
