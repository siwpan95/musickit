# 📻 radio 并入 musickit —— 合并说明

原 `G:\music\radio` 已整体并入 `G:\music\musickit\radio\`（2026-08-20）。

## 音源变化

原来的 `G:\music\radio\music`（本地歌曲目录）已被移除，不再使用。
电台的默认音源改为 **musickit 随机渲染**：

- 渲染器：`remix/tools/musickit_render_one.py`（随机混音师签名 × 随机流派提示词 × 随机 stems，输出 MP3 + JSON 元数据）
- 电台侧：`radio/radio/musickit_source.py`（后台预渲染线程 + 就绪队列，子进程调用渲染器，引擎崩溃不影响电台）
- 广播者：`broadcaster._run_musickit`（渲染好的 MP3 走原有推流管线，ICY/HLS/多码率/录音全部兼容）
- 控制面板：右侧「🎲 musickit 随机渲染」区（开始/停止/频道 slug/每曲小节数）
- API：`POST /api/musickit`（`{"action":"start"|"stop", "channel":"random", "bars":32}`）
- 状态：`GET /api/status` 的 `musickit` 字段（active/rendering/channel/queued/rendered_count/last_error）

## 运行

```bash
python G:\music\musickit\radio\run.py            # 默认即随机渲染，首曲约 15~30 秒渲染后开播
python G:\music\musickit\radio\run.py --expose   # + cloudflared 公网穿透
```

引擎依赖（F:/Python314 已装）：pydub numpy scipy soundfile audioop-lts。

## 主要配置（radio/radio/config.py F 层）

| 配置 | 默认 | 说明 |
|------|------|------|
| `DEFAULT_SOURCE` | `"musickit"` | 默认音源（`"playlist"` = 传统 music/ 歌单） |
| `MUSICKIT_ROOT` | musickit 仓库根（自动推算，可用环境变量覆盖） | 渲染器/素材位置 |
| `MUSICKIT_RENDER_CHANNEL` | `"random"` | 混音师频道 slug（random = 每曲随机） |
| `MUSICKIT_RENDER_BARS` | `32` | 每曲小节数（32 小节 ≈ 100 秒） |
| `MUSICKIT_RENDER_FUSION` | `True` | 提示词跨类融合 |
| `MUSICKIT_RENDER_RELEASE_SAFE` | `False` | 仅 free/pack 授权素材 |
| `MUSICKIT_RENDER_QUEUE_DEPTH` | `3` | 预渲染就绪队列深度 |
| `MUSICKIT_RENDER_KEEP` | `20` | 渲染缓存保留文件数（`radio/render_cache/`） |
| `MUSICKIT_RENDER_PYTHON` | 当前解释器 | 渲染子进程解释器 |

## 其他

- 传统歌单模式仍可用：往 `radio/music/` 放歌，面板切回歌单模式（或 `stop_musickit`）。
- 点歌/随机播放开关仅对歌单模式生效；转播（relay）功能不变。
- 浏览器扩展 / Android APK 均指向电台服务地址，无需改动。
