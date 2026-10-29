# <PATH> — phonk 混音项目（真实采样 + 本地混音引擎）

## 仓库角色定位（投资组合分级 ①）

> 本仓在 siwpan 投资组合（D:/projects/repos，共 133 仓）中定级为 **① 核心推进**，领域 **音乐/音频**，定位 **本地音乐流水线**。
> **角色**：phonk 混音项目（真实采样+本地混音），持续投入。
> **维护策略**：① 核心推进——持续投入、不允许冻结；随所属收敛点 / 流水线长期演进。
> 投资组合统一分级索引：`D:/projects/repos/PORTFOLIO_TIERING.md`。

> 仓库：<https://gitee.com/siwpan/musickit> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 端口登记（2026-08-24）：mixer 流服务 **8010**（remix/tools）已登记于 `<PATH>`；remix 任务日志审计 `python remix/main.py --tasks --out <目录>`。

## 目录结构

```
musickit/
├── bass/          # 贝斯：整曲 stem（radio/csmusic）+ 免费包 loop/one-shot（sub_bass/808 等子类）
├── drum/          # 鼓：整曲 stem + 打击 one-shot/loop（drums_acoustic/percussion/hihat 等子类）
├── guita/         # 旋律轨：Demucs other 轨（有意当吉他轨，项目约定）+ 真吉他 loop 包
├── cowbell/       # 牛铃 one-shot（Mixkit）
├── synth/         # 合成器 loop/one-shot（SampleRadar 等，100% 真实采样）
├── acapella/      # 真人声池（Coollider Acapellas Vol.1-42 + vocal_chops 人声切片包）
├── animal/        # 动物叫声 one-shot（随机混音的人声切片替代层，不再混入人声包）
├── sfx/           # riser/impact/过渡音效（Mixkit + 采样包）
├── keys/          # 钢琴/风琴/手风琴/竖琴/钟琴（含 loop 与单音采样，单音仅作回退）
├── strings/       # 弦乐（bowed 等）
├── brass/         # 铜管/萨克斯
├── woodwind/      # 木管/笛箫（大量单音采样；旋律层选音优先 loop，见下）
├── ethnic/        # 民族乐器（拨弦/拉弦/打击）
├── archived/      # 🗑️ 垃圾桶/归档区：只进不出（见 archived/README.md）
├── music/         # 风格提示词生成器（65 流派风格池）+ 提示词→混音桥接器
├── burbidge_album/# 固定风格专辑管线：同一 stems × 24 位混音师签名链（mixer_styles.py）
├── remix/         # 混音应用（main.py + core/gui/utils/tools/tests + 内置 ffmpeg）
│                   # tools/ 含混音师电台 mixer_radio.py 与本地流服务 mixer_stream.py
├── radio/         # 📻 电台输出端（管线终点）：纯 Python+Flask 24/7 推流，
│                   # 默认音源=musickit 随机渲染；2026-09-02 从历史 93db08f~1 还原，
│                   # 与 private-radio-stations apps/audio（Node 转播版）并存
├── instrument_taxonomy.json   # 规范乐器分类体系：242 乐器词 → 37 类目 → 13 池
├── manifest_index.json        # 总索引（自动化每 6h 重建，不入版本库）
└── README.md / INTEGRATION.md / EVALUATION_REPORT.md / FIX_PLAN.md /
    MUBERT_RESEARCH.md / MUBERT_METHODOLOGY.md / MUBERT_COMPARISON.md
```

## 素材授权（license_tier，写入各池 manifest.json）

| tier | 含义 | 混音默认 | --release-safe |
|------|------|---------|----------------|
| `free` | 可免费商用（Mixkit、MusicRadar SampleRadar） | ✅ 用 | ✅ 用 |
| `pack` | 商业采样包（EULA 允许音乐制作与发布成品；样本勿转售） | ✅ 用 | ✅ 用 |
| `restricted` | 商业歌曲 Demucs stem / 粉丝提取游戏音乐（仅个人练习与研究） | ✅ 用（个人用途） | ❌ 剔除 |
| `unknown` | 来源未记录 | ✅ 用（个人用途） | ❌ 剔除 |

- 授权治理脚本：`remix/tools/tag_license_tiers.py`（标注 tier + 补全 license，备份在
  `archived/manifest_backup_20260817/`）、`remix/tools/audit_licenses.py`（巡检分布）。
- **发布前请用 `--release-safe` 跑一次**：它只从 free/pack 素材选音，
  彻底避开商业歌曲 stem 与来源不明素材。

## 混音（remix）

```bash
（cd remix）
python <PATH> --remix                                          # 默认 3 轨骨架、32 小节、BPM 随机
python <PATH> --remix --count 5 --bars 64 --bpm 140 --format wav
python <PATH> --remix --structure classic_drop --seed 42 --out output
python <PATH> --remix --release-safe                           # 发布安全模式（仅 free/pack 素材）
python <PATH> --remix --mixer-style wallace                    # 混音师风格着色（24 位，见下）

usage: main.py [-h] [--remix] [--count COUNT] [--seed SEED] [--bars BARS] [--bpm BPM]
               [--structure STRUCTURE] [--out OUT] [--format {wav,mp3,ogg,flac}]
               [--release-safe] [--mixer-style {24位混音师slug|random}]
```

**选音规则（2026-08-17 起）**：

- 骨架层（drum/bass/guita）**保底挑选 ≥1 小节的 loop/stem**（manifest 时长优先，
  未知时长则 stem 命名优先 + ffprobe 抽样探测），混音时强制循环层——
  杜绝 one-shot 被抽成唯一鼓轨导致整曲失去律动；
- 牛铃/synth/animal/sfx 为点缀层（各最多 1 条）；输出 >12 小节时按曲式模板编排
  intro→drop→outro，A/B 变体防单调；
- 整曲 stem → 能量峰定位切 1~2 小节 loop；源 BPM 已知或可估计时 atempo 对齐（钳制 0.85~1.18）；
- 输出文件名同秒冲突自动递增（`_1/_2`），不会覆盖旧产物；
- `MUSICKIT_ROOT` 环境变量可覆盖素材根目录。

测试：`python -m pytest tests -q`（**112 passed, 1 skipped**）；快速档 `python -m pytest tests -q -m smoke`
（16 个纯逻辑用例）。Python 3.13+ 需 `audioop-lts`；混音师风格链需 `scipy` + `soundfile`（均已在 requirements.txt）。

## 提示词驱动混音（来自 <PATH>，同仓整合）

`<PATH>` 把风格提示词经
`instrument_taxonomy.json`（242 词 → 37 类目）映射为本引擎调用：

- 乐器词 → 池 + 角色：鼓/贝斯角色与引擎同口径**保底 ≥1 小节 loop**；
  旋律层（keys/strings/brass/woodwind/ethnic/guita/synth）**优先 loop/BPM 显式素材**、
  排除单音采样（如 "EHn_susDyn_..._D3"），最后才全量回退；
- 无样本/无匹配的乐器记入 `gaps`，绝不假映射；
- 曲式模板选择规则外置在 `structure_moods.json`（改词表无需改代码）；
- 支持 `--release-safe`（与引擎同口径过滤）。

## 固定风格专辑与混音师频道（burbidge_album）

burbidge_album/ 是固定风格管线：同一组 stems × **24 位混音师签名链**（burbidge /
ghenea / clearmountain / marroquin / pensado / blake / lordalge / schmitt / mikedean /
stent / wallace / maserati / joshua / ali / elmhirst / scheps / moulder / guzauski /
albini / everett / elevado / shebib / power / zhoutianche），每位经共享模块
mixer_styles.py 参数化（逐总线 EQ/压缩/饱和/混响/宽度 + 风格母带），两条管线共用：

- 专辑：python burbidge_album/build_album.py（全量）或 ... wallace maserati（增量）
  → album/<slug>/ 成品 + 试听页；album/channels.json 为 24 频道目录；
- 随机混音接入：python main.py --remix --mixer-style joshua
  或 python music/prompt_driven_remix.py --mixer-style random；
- 频道形态（类 Mubert）：python remix/tools/mixer_radio.py --channel wallace --count 3
  （本地电台，输出 m3u8）；python remix/tools/mixer_stream.py --port 8010
  （本地无限流：/api/channels /api/stream/<slug> /api/track/<slug>）。

设计与 Mubert 的异同及频道可行性详见 MUBERT_COMPARISON.md，整合总览见 INTEGRATION.md。

## 采样源（与 license_tier 对应）

| 源 | 内容 | tier |
|----|------|------|
| `<PATH>` | 商业歌曲 Demucs 分离 stem（bass/drum/guita 编号 1~258） | restricted |
| `<PATH>` | CS 游戏音乐粉丝提取 stem（编号 >=726，自动化并入） | restricted |
| `<PATH>` | 商业采样包（Black Octopus/XAM/Singomakers/Loopmasters 等） | pack |
| Mixkit / MusicRadar SampleRadar | 免费可商用素材 | free |

## archived 定位（固化）

`archived/` 是项目的**垃圾桶/归档区**：只进不出、不参与混音、移动而非删除
（记录在 `dedupe_manifest.json` / `moved_vocal_packs_*.json` / `manifest_backup_*/`）。
详见 `archived/README.md`。

## 版本控制

`git`（gitee 仓库 `siwpan/musickit` 分支 `master`，本地同步工作区 `<PATH>`）：
素材音频不入库（仅各池 `manifest.json`），代码 / 文档 / manifest 全部跟踪；
成品 wav/mp3、_stretch_cache/、prompt_mixes/、remix/output/ 由 .gitignore 排除。


---

## 仓库索引标注（2026-08-27 · siwpan 统一治理）

> musickit（phonk 混音项目，独立仓 siwpan/musickit）；本地对应 <PATH>。
> 电台融合实验记录见 RADIO_MERGE.md；提示词生成器为独立仓 siwpan/music-prompt-generator。
> **2026-09-02**：radio/ 直播端已从历史还原（93db08f~1）——此前被误判冗余移除；它与
> private-radio-stations apps/audio（Node **转播版**）功能面不同（直播 vs 转播），非冗余，并存。
> 本标注为发布面统一追加，不改变原有内容。
