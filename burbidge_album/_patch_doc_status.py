# one-shot: update MUBERT_COMPARISON.md L1-L3 status + INTEGRATION.md tools
p1 = r'G:/music/musickit/MUBERT_COMPARISON.md'
src = open(p1, encoding='utf-8').read()

old = '''- **L1 静态频道页**（已完成约 90%）：album/<slug>/index.html 即频道页，总览页即频道列表。补一个「频道元数据 JSON 目录」（从 styles_manifest.json 直接生成）即可对齐 Mubert 频道目录概念。成本 ≈ 0。
- **L2 本地混音师电台**（建议先做）：新增 tools/mixer_radio.py —— CLI 指定 --channel <slug>，后台循环「随机提示词 → 该频道混音 → 追加播放队列 + 输出 .m3u」，用任意播放器顺序播放即得「Wallace 电台 / Schmitt 电台」。成本：半天；价值：直接验证 5.1 的频道体验假设。
- **L3 类 Mubert 流服务**：本地 HTTP 服务（FastAPI/标准库均可）+ ffmpeg 转 HLS 切片，端点 /api/channels、/api/stream/<slug>、/api/track/<slug>?seed=N。频道 API 概念对齐 Mubert（genre=混音师、mood=流派）。成本：1~2 天，零外部依赖。
- **L4 云化/商业化**：需先解决三件事——授权（发布侧强制 --release-safe，已有）、频道叙事合规（见 5.5）、托管与订阅计费。成本与风险显著上升。'''
new = '''- **L1 静态频道页** ✅ 已落地：album/<slug>/index.html 频道页 + 总览页 + album/channels.json 频道目录（24 频道元数据，generate_album_docs.py 自动生成）。
- **L2 本地混音师电台** ✅ 已落地：remix/tools/mixer_radio.py —— --channel <slug> 固定频道（random = 每曲随机混音师），循环「随机流派提示词 → 该频道混音 → 追加 .m3u8 播放列表 + radio_report.json」，任意播放器顺序播放即电台。实测 2 曲 103s 音频用时 89s。
- **L3 类 Mubert 流服务** ✅ 已落地：remix/tools/mixer_stream.py —— 本地 HTTP（仅标准库），频道主页（24 卡片 + <audio>）、/api/channels、/api/stream/<slug>（连续 MP3 帧无限流，首曲渲染后即播）、/api/track/<slug>?seed=N、/api/playlist/<slug>。实测 5 端点全 200，无限流连续推流。
- **L4 云化/商业化** ⏸ 暂缓（按结论）：待授权（--release-safe 已具备）与频道叙事合规（5.5）确认后再决策。'''
assert src.count(old) == 1
src = src.replace(old, new, 1)

old2 = '''建议路径：先落 L1（频道目录 JSON，半小时）与 L2（mixer_radio.py 本地电台，半天），用「频道一致性体验」实测验证；L3 按需 1~2 天实现本地流服务；L4 云化在授权与叙事合规确认后再决策。'''
new2 = '''落地状态：L1/L2/L3 已于 2026-08-19 全部实现并实测（频道目录 JSON、mixer_radio.py、mixer_stream.py）；L4 云化待授权与叙事合规确认。'''
assert src.count(old2) == 1
src = src.replace(old2, new2, 1)
open(p1, 'w', encoding='utf-8').write(src)
print('MUBERT_COMPARISON.md updated')

p2 = r'G:/music/musickit/INTEGRATION.md'
src = open(p2, encoding='utf-8').read()
old3 = '''## 扩展混音师'''
new3 = '''## 混音师频道（Mubert 形态对齐）

- remix/tools/mixer_radio.py：本地混音师电台（--channel wallace --count 3，输出 m3u8 播放列表 + 报告）
- remix/tools/mixer_stream.py：本地流服务（http://127.0.0.1:8010/，频道主页 /api/channels /api/stream/<slug> /api/track/<slug>）
- burbidge_album/album/channels.json：24 频道目录（generate_album_docs.py 自动生成）
- 详见 MUBERT_COMPARISON.md 第五章可行性专题

## 扩展混音师'''
assert src.count(old3) == 1
src = src.replace(old3, new3, 1)
open(p2, 'w', encoding='utf-8').write(src)
print('INTEGRATION.md updated')
