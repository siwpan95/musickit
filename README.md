# <PATH> — phonk 混音项目（真实采样 + 本地混音引擎）

## 仓库角色定位（投资组合分级 ①）

> 本仓在 siwpan 投资组合（D:/projects/repos，共 133 仓）中定级为 **① 核心推进**，领域 **音乐/音频**，定位 **本地音乐流水线**。
> **角色**：phonk 混音项目（真实采样+本地混音），持续投入。
> **维护策略**：① 核心推进——持续投入、不允许冻结；随所属收敛点 / 流水线长期演进。
> 投资组合统一分级索引（多机可查）：[组合分级决策索引 · allin 事实源](https://gitee.com/siwpan/allin/blob/master/docs/事实源/组合分级决策索引.md)。

> 仓库：<https://gitee.com/siwpan/musickit> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

> 端口登记（2026-08-24）：mixer 流服务 **8010**（remix/tools）已登记于 `<PATH>`；remix 任务日志审计 `python remix/main.py --tasks --out <目录>`。

> 👋 **第一次接触本仓库？** 请先读 **[新人开发上手指南 · ONBOARDING.md](ONBOARDING.md)** ——
> 环境准备、代码获取、素材补齐、启动各模块、常见问题、贡献规范，全部命令均经实测。
> 本 README 讲「有什么」，ONBOARDING 讲「怎么跑起来」。

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
├── remix/         # 混音应用（main.py + core/gui/utils/tools/tests；ffmpeg/ffprobe 需自备，见下）
│                   # tools/ 含混音师电台 mixer_radio.py 与本地流服务 mixer_stream.py
├── radio/         # 📻 电台输出端（管线终点）：纯 Python+Flask 24/7 推流，
│                   # 默认音源=musickit 随机渲染；2026-09-02 从历史 93db08f~1 还原，
│                   # 与 private-radio-stations apps/audio（Node 转播版）并存
├── instrument_taxonomy.json   # 规范乐器分类体系：242 乐器词 → 37 类目 → 13 池
├── manifest_index.json        # 总索引（自动化每 6h 重建，不入版本库）
├── docs/         # 文档归类区
│   ├── musickit-architecture.html   # 架构设计文档（§7 能力补全建议的源头）
│   ├── INTEGRATION.md               # 双管线整合总览（固定风格 × 随机风格）
│   ├── MUBERT_RESEARCH.md           # Mubert 调研报告
│   ├── MUBERT_METHODOLOGY.md        # Mubert 方法论移植
│   ├── MUBERT_COMPARISON.md         # Mubert 对比报告
│   ├── EVALUATION_REPORT.md         # 项目评估报告（2026-08-13）
│   ├── FIX_PLAN.md                  # 修复计划（v2）
│   ├── RADIO_MERGE.md               # radio 并入说明
│   └── 深度评估_20260817.md / 深度评估_更正_20260817.md
└── README.md / ONBOARDING.md（新人上手指南）/ SKILL.md
```

## 素材授权

**本项目素材均为公共领域（Public Domain），可自由用于制作与发布。**

> ⚠️ **`--release-safe` 已于 2026-11-02 废弃**：它按 manifest 的 `license_tier` 过滤，
> 但该字段严重失真（30,259 条中 `unknown` 占 64.7%、`restricted` 仅 3.6%），
> 而实际素材全为公版。该开关只放行 `free`+`pack`（31.7%），等于无谓砍掉 68.3% 素材，
> 且其过滤逻辑曾被 B 变体（`bars>12` 换素材）绕过 —— 保护为零、代价很大。
> 现已改为**不做任何过滤**：参数仍接受（兼容旧脚本），但不再影响选音。

公版素材来源参考（可自行扩充）：

| 站点 | 内容 | 说明 |
|------|------|------|
| <https://freepd.cn/music> | FreePD 中文镜像 · 公共领域音乐 | 免注册直下，适合做 stem 源 |
| <https://freepd.com> | FreePD 原站（CC0） | 经典/氛围/电子分类齐全 |
| <https://mixkit.co/free-stock-music> | Mixkit 免费音乐 | 免费商用，无需署名 |
| <https://freesound.org> | Freesound（按 CC0 筛选） | one-shot / 环境音最全 |

历史遗留字段 `license_tier` 仍保留在 manifest 中，但**不再参与任何判定**。
相关脚本 `remix/tools/tag_license_tiers.py`、`audit_licenses.py` 仅作历史参考。

### 素材入库（整曲 → stem → 池）

`bass / drum / guita / acapella` 四个池要的是**分离后的 stem**，而公版站给的是整曲。
两步走（2026-11-02 实测可用）：

```bash
# 1) 抓公版曲（CC0；服务端渲染页，直链支持 Range）
python remix/tools/fetch_freepd.py --out D:/tmp/freepd_src --limit 4
python remix/tools/fetch_freepd.py --out D:/tmp/freepd_src --list      # 只列出不下载

# 2) 归一化 → demucs 四轨 → 分池落盘 + 更新 manifest
python remix/tools/ingest_stems.py --src D:/tmp/freepd_src --source-tag freepd
python remix/tools/ingest_stems.py --demucs-out D:/tmp/demucs_out      # 复用已分离产物
python remix/tools/ingest_stems.py --src ... --dry-run                 # 只看计划

# 按来源标签整批撤回（拿本地曲库做测试素材后的后悔药）
python remix/tools/ingest_stems.py --purge-tag ftest --dry-run          # 先看会删什么
python remix/tools/ingest_stems.py --purge-tag ftest                    # 真删
```

| 项 | 说明 |
|---|---|
| stem 映射 | `drums→drum`、`bass→bass`、`other→guita`、`vocals→acapella` |
| 落盘命名 | `<source_tag>__<曲名>.wav`（stem 类型由所在池隐含） |
| manifest | 按 basename upsert，写入 `sha256 / duration_s / license / content_kind=stem` |
| 幂等 | 目标文件已存在且 sha256 相同则跳过 |
| 依赖 | `torch` + `demucs`（`--python` 可指定装它们的解释器；本机 `E:\Python314` 已装） |
| 实测成本 | CPU 分离约 **1.2× 实时**（240s 曲 ≈ 3.3 分钟/首） |

> 输入会先用 ffmpeg 归一化为 44.1k/2ch/16bit WAV 再送 demucs —— demucs 自带加载器
> 对部分 mp3 流会报 `malformed stream: mpa: invalid main_data offset`，且其 ffmpeg 回退
> 在本机识别不到，归一化可同时绕开这两个问题。
>
> 音频本身仍被 `.gitignore` 排除，只有 `manifest.json` 入库。

### 乐器池入库（单音 one-shot，爱荷华 MIS）

`keys / strings / brass / woodwind / ethnic` 五个池长期是「manifest 里上万条索引、
磁盘上 0 个文件」—— 那些条目指向商业采样包，音频本体从没进过仓库，选音时等于无米下锅。

[University of Iowa Musical Instrument Samples（MIS）](https://theremin.music.uiowa.edu/MIS.html)
是实测可下、且**一份覆盖四个池**的公版源：站点自 1997 年公开，原话
*"may be downloaded and used for any projects, without restrictions"*（无 NC、无强制署名）。
内容是**每个音一条单音 one-shot**，不用拆 SoundFont。

```bash
# 先看计划（不下载）
python remix/tools/fetch_iowa_mis.py --limit 2 --dry-run

# 四池各下 10 条
python remix/tools/fetch_iowa_mis.py --instruments piano violin trumpet flute --limit 10

# 13 件乐器一次铺开（弦乐/铜管/木管/键盘）
python remix/tools/fetch_iowa_mis.py --instruments piano violin viola cello doublebass \
    trumpet frenchhorn trombone tuba saxophone flute oboe clarinet bassoon --limit 10
```

| 项 | 说明 |
|---|---|
| 覆盖 | 弦乐 violin/viola/cello/doublebass、铜管 trumpet/frenchhorn/trombone/tuba/sax、木管 flute/oboe/clarinet/bassoon、键盘 piano |
| 落盘 | 平铺在池根，`iowa__<原文件名>.wav`（池子的既有约定：文件在根，靠 `subcategory` 分类） |
| 转码 | AIFF → 44.1kHz/16bit WAV；保持原声道（`audio_loader` 会按目标声道统一，不必强上立体声） |
| 选取 | 默认**等距**抽取，不是取前 N 条 —— 页面按力度/奏法分组，取前 N 会全挤在同一个力度、音域也偏低 |
| manifest | 写 `source_pack / original / original_rel / license 原文 / source_url / duration_s / sha256`，`content_kind=oneshot` |
| **`key` 只按文件名写单音** | 除钢琴外文件名是**音域范围**（`Violin.arco.pp.sulG.G3B3.aiff` 表示覆盖 G3~B3），根音不明确 —— 按起点猜音级会污染 `--key`，所以范围样本不写。单音文件（`Piano.ff.B5.aiff`）直接写 `key: "B"` + `key_pitch_only: true`，选音时走「只比音级」的兼容判定（`musical_key.rank_pitch`）。为什么不信 chroma：实测 `Piano.ff.B5` 被判成 C#m（conf 0.38 / margin 0.05），高音区泛音把音级带偏了，而文件名是准的 |
| 幂等 | 目标文件已存在则跳过；`--force` 重下重转 |
| 缓存 | 原始 AIFF 存在 `%TEMP%/musickit_iowa`，可 `--cache` 指定 |

> 缺口：**ethnic（民族乐器）没有可用的公版源**。FreePats 的 ethnic 目录只有卡林巴/口弦琴，
> 二胡/古筝/笛子/唢呐这类不存在；archive.org 与 GitHub 在本机不可达。
> FreePats 另有 CC0 立式钢琴（`UprightPianoKW`）与竖琴，可作为 keys 的补充，但需 7-Zip 解包。

### 调性标注与 `--key`（T2-1）

提示词里的 `scale` 一直是「只读不用」的字段（详见架构文档 §7）。T2-1 先做**不做
pitch-shift 的最小闭环**：给素材标调性，选音时优先挑兼容的，避免调性打架。

```bash
# 1) 估计每个素材的调性（librosa chroma + Krumhansl 轮廓），写回 manifest
python remix/tools/detect_keys.py                 # 只补缺 key 的
python remix/tools/detect_keys.py --force         # 全部重算
python remix/tools/detect_keys.py --pools bass guita --dry-run

# 2) 混音时指定目标调性
python remix/main.py --remix --key Am             # 完整调性（含主音）
python remix/main.py --remix --key 小调           # 只给调式（无主音）
```

| 概念 | 说明 |
|---|---|
| 兼容等级 | 同调(0) → 关系大小调(1) → 纯五/四度(2) → 同主音大小调(3) → 不兼容(9) |
| 未知调性 | 排在「已知可用」之后、「确定不兼容」之前（可能合也可能不合） |
| **只重排、不删除** | 池子小的时候硬过滤会直接选不出音，故降级使用并在日志报告各档计数 |
| 调式名 | `scale` 是调式（小调/多利亚/布鲁斯/大调/利底亚…），无主音 → 只比色彩 |
| 仅标注有音高的池 | bass/guita/keys/strings/brass/woodwind/ethnic/synth/acapella；drum/cowbell/animal/sfx 无调性 |

> 提示词驱动路径已透传：`prompt_driven_remix.py` 把 `data["scale"]` 作为 `key=` 传给引擎，
> 于是「小调」类提示词会优先挑小调素材，「五声 / 无调性」不做任何偏好。

## 混音（remix）

```bash
（cd remix）
python <PATH> --remix                                          # 默认 3 轨骨架、32 小节、BPM 随机
python <PATH> --remix --count 5 --bars 64 --bpm 140 --format wav
python <PATH> --remix --structure classic_drop --seed 42 --out output
python <PATH> --remix --mixer-style wallace                    # 混音师风格着色（24 位，见下）

usage: main.py [-h] [--remix] [--count COUNT] [--seed SEED] [--bars BARS] [--bpm BPM]
               [--structure STRUCTURE] [--out OUT] [--format {wav,mp3,ogg,flac}]
               [--mixer-style {24位混音师slug|random}]
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

测试：`python -m pytest remix/tests music/tests -q`（**343 用例**，2026-11-02 实测；引擎侧 285 /
桥接器侧 58）；快速档 `python -m pytest remix/tests music/tests -q -m smoke`（**221 个纯逻辑用例**，
无 ffmpeg 编解码、无真实素材依赖）。一行走完自检 + 冒烟：`bash scripts/ci_smoke.sh`。
Python 3.13+ 需 `audioop-lts`；混音师风格链需 `scipy` + `soundfile`（均已在 requirements.txt）。
ffmpeg / ffprobe 需自备（`remix/bin/` 或系统 PATH，解析见 `remix/core/binfind.py`）。

> 注：`music/test_suite.py` 是**评测报告生成器**（打印检查点并通过率），不是 pytest 用例；
> 其产物 `TEST_REPORT.md` / `demo_test.*` 均已在 .gitignore 内，不入版本库。

## 自检与冒烟（本地 / CI 通用）

```bash
python remix/tools/doctor.py        # 环境 + 素材一致性自检（0 通过 / 1 告警 / 2 硬失败）
bash scripts/ci_smoke.sh            # 自检 + 冒烟测试（CI 只需调这一个）
PYTHON=/e/Python314/python.exe bash scripts/ci_smoke.sh   # 指定解释器
FULL=1 bash scripts/ci_smoke.sh     # 附带全量单测
```

`ci_smoke.sh` 依次跑：环境自检 → 文档数字一致性 → **编码门禁** → 冒烟测试。
其中编码门禁要求 `remix/`、`music/` 与 `radio/` 下**文本模式**的 `open()` 必须显式写
`encoding="utf-8"` —— Windows 上 `open()` 默认用 locale 编码（中文系统是 GBK），
写中文内容（中文路径 / 素材标题 / ID3 注释 / manifest 里的中文 license 文本）
会写出乱码或直接 `UnicodeEncodeError`。二进制模式**不要**加 `encoding=`。

`doctor.py` 会打印每个素材池的「manifest 条目数 / 磁盘文件数 / 缺失数」——
干净克隆下 13 个池全为 0（素材被 .gitignore 排除，属预期），此时退出码为 1（告警而非失败）。

> CI 接入：Gitee Go 新建流水线，构建脚本填 `bash scripts/ci_smoke.sh` 即可。
> 本仓暂**未**提交 `.workflow/*.yml` —— Gitee Go 的流水线 YAML 需在仓库实际开启后
> 按平台当前版本核对字段，避免提交一份跑不起来的配置。

## 提示词驱动混音（来自 <PATH>，同仓整合）

`<PATH>` 把风格提示词经
`instrument_taxonomy.json`（242 词 → 37 类目）映射为本引擎调用：

- 乐器词 → 池 + 角色：鼓/贝斯角色与引擎同口径**保底 ≥1 小节 loop**；
  旋律层（keys/strings/brass/woodwind/ethnic/guita/synth）**优先 loop/BPM 显式素材**、
  排除单音采样（如 "EHn_susDyn_..._D3"），最后才全量回退；
- 无样本/无匹配的乐器记入 `gaps`，绝不假映射；
- 曲式模板选择规则外置在 `structure_moods.json`（改词表无需改代码）；
- ~~支持 `--release-safe`~~ → 该开关已于 2026-11-02 废弃（素材全为公版，不再过滤）。

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

设计与 Mubert 的异同及频道可行性详见 [docs/MUBERT_COMPARISON.md](docs/MUBERT_COMPARISON.md)，整合总览见 [docs/INTEGRATION.md](docs/INTEGRATION.md)。

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
> 电台融合实验记录见 [docs/RADIO_MERGE.md](docs/RADIO_MERGE.md)；提示词生成器为独立仓 siwpan/music-prompt-generator。
> **2026-09-02**：radio/ 直播端已从历史还原（93db08f~1）——此前被误判冗余移除；它与
> private-radio-stations apps/audio（Node **转播版**）功能面不同（直播 vs 转播），非冗余，并存。
> 本标注为发布面统一追加，不改变原有内容。
