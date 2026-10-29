# Remix — 音频混音（musickit 专属版）

> 本版本为 musickit 专用改造版，**已移除视频合成功能**，仅保留音频混音，
> 并新增「从 bass / drum / guita 随机选音混音（phonk 风格）」的命令行模式。

一个用 Python + pydub 实现的桌面音频混音器。
支持多轨混音、分轨增益、软/硬削波、峰值/RMS 归一化、淡入淡出、
交叉淡化、动态压缩、高低通滤波。

## ⚠️ 环境要求（重要）

### 1. ffmpeg 必须安装且在 PATH 中
pydub 只是 ffmpeg 的封装，**没有 ffmpeg 程序本工具无法运行**。

- 下载：https://ffmpeg.org/download.html
- 安装后确认命令行能执行 `ffmpeg -version` 和 `ffprobe -version`

### 2. Python 版本与 audioop
- **Python ≤ 3.12**：`pip install -r requirements.txt` 即可。
- **Python 3.13 / 3.14（及更高）**：标准库已移除 `audioop` 模块，
  而 pydub 运行依赖它。**必须安装 `audioop-lts` 补丁包**（已写入
  `requirements.txt`，但务必确认安装成功）。若缺少会报
  `ModuleNotFoundError: No module named 'audioop'`。

### 3. scipy / soundfile（混音师风格链）
--mixer-style 与 burbidge_album 共享链依赖 scipy（信号处理）与 soundfile（音频读写），
已写入 requirements.txt。现役环境 /Python314 已装齐（scipy 1.18 / soundfile 0.14）。

## 安装

```bash
# 建议使用虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt

# 验证依赖
python -c "import pydub, audioop; print('OK')"   # 3.13+ 应能看到 audioop 来自 audioop-lts
```

## 运行

```bash
python main.py
```

启动后有一个标签页：

- **音频混音**：添加多个音频文件 → 设置增益/削波/归一化/淡入淡出/交叉淡化/
  压缩/滤波 → 开始混音 → 输出到 `output/mixed_output.<fmt>`。

## 随机混音（phonk 风格，命令行 · loop 化 beat）

从与 `remix` 同级的 musickit 素材目录（`bass`/`drum`/`guita`/`cowbell`/`synth`）
随机抽取音轨，**按 BPM 网格切 loop 编排成固定小节数的 beat**：

- 整曲 stem（≥4 小节）→ 能量峰定位 + 切 1~2 小节 loop；
- 短 loop / one-shot → 整段使用，循环铺满或每 2 小节点缀；
- 输出默认 **16 小节**（约 27s@140BPM），远小于旧版的整曲叠加。

```bash
# 默认 3 轨（drum+bass+guita 最小骨架）、16 小节、BPM 随机 110~150
python main.py --remix

# 5 轨 / 8 小节 / 固定 140BPM / mp3 输出
python main.py --remix --count 5 --bars 8 --bpm 140 --format mp3

# 固定种子可复现
python main.py --remix --seed 42 --bars 16 --out output

# 发布安全模式：仅使用授权层级 free/pack 的素材（restricted/unknown 一律剔除）
python main.py --remix --release-safe
```

**混音师风格着色（--mixer-style，可选；不传时行为不变）**：

    python main.py --remix --mixer-style mikedean            # 固定某位混音师签名
    python main.py --remix --mixer-style random --seed 42    # 随机一位（可复现）

- 24 位混音师：burbidge / ghenea / clearmountain / marroquin / pensado / blake /
  lordalge / schmitt / mikedean / stent / wallace / maserati / joshua / ali / elmhirst /
  scheps / moulder / guzauski / albini / everett / elevado / shebib / power / zhoutianche
  （每位签名与逐总线参数见 burbidge_album/album/ALBUM_NOTES.md）；
- 共享注册表：burbidge_album/mixer_styles.py（与固定风格专辑管线同源）；
- 效果：鼓/贝斯/铺垫/主奏人声分轨过对应总线链，母带走风格链（峰值 -1.5 dBFS 留编码余量）。

**选音规则（2026-08-17 起）**：
- 骨架层（drum/bass/guita）**保底挑选 >=1 小节的 loop/stem**（manifest 时长优先，
  未知时长则整曲 stem 命名优先 + ffprobe 抽样探测），混音时强制循环层，
  杜绝 one-shot 被抽成唯一鼓轨导致整曲失去律动；
- `--release-safe`：按各池 manifest 的 `license_tier` 过滤，只留 free/pack。

素材根目录可用环境变量 `MUSICKIT_ROOT` 覆盖（默认 remix 的上级目录）。

**目录约定**：
- `guita/` = Demucs 分离的 other 轨，**有意作为吉他/旋律轨使用**（项目约定）
- `archived/` = 垃圾桶/归档区（冗余副本、占位音频、下载暂存），不参与混音
- 各素材目录下的 `manifest.json` 记录编号 → 来源 → 授权，可溯源

**phonk 风格参考（联网调研）**：典型 phonk beat 由多层构成 ——
鼓组（1~2 轨）、808 贝斯（1 轨）、牛铃 / 旋律采样（1 轨）、人声切片（可选）、
其它 synth / 采样。最小可用骨架为 3 轨（鼓 + 贝斯 + 旋律），
典型完整制作约 4~6 轨。本工具默认随机选 3 条，可用 `--count` 调整。

## 混音师频道（类 Mubert 频道形态，详见 MUBERT_COMPARISON.md L1~L3）

    python tools/mixer_radio.py --channel wallace --count 3     # 本地混音师电台 -> <slug>_radio.m3u8
    python tools/mixer_stream.py --port 8010                    # 本地无限流服务（浏览器即播）

- tools/mixer_radio.py：固定混音师签名 × 随机流派提示词，连续产出 + m3u8 播放列表 + radio_report.json；
- tools/mixer_stream.py：频道主页（24 卡片）、/api/channels、/api/stream/<slug>（连续 MP3 无限流）、
  /api/track/<slug>?seed=N、/api/playlist/<slug>，仅标准库实现；
- 频道目录：burbidge_album/album/channels.json（generate_album_docs.py 自动生成）。

## 每小时自动混音（tools/hourly_remix.py）

「每小时一首随机风格、固定两分钟」的无人值守驱动，主路径复用 `main.py --remix` **自带的随机混音**
（phonk 风格随机选曲 + 随机 BPM + 随机曲式模板）——即"随机风格"本意，不含提示词驱动的复杂链路；
`--fusion` 为可选进阶路径（走 `music/` 提示词链 + **跨类融合**，随机混搭两类、乐器/情绪去重）。

```bash
/Python314/python.exe tools\hourly_remix.py                       # 随机风格 × 2 分钟（全素材池，发布安全默认关）
/Python314/python.exe tools\hourly_remix.py --mixer-style random  # 叠加随机混音师染色
/Python314/python.exe tools\hourly_remix.py --fusion             # 进阶：提示词跨类融合（随机混搭两类）
/Python314/python.exe tools\hourly_remix.py --count 5 --bpm 140  # 固定 5 轨 / 140BPM
/Python314/python.exe tools\hourly_remix.py --seed 42             # 可复现
/Python314/python.exe tools\hourly_remix.py --dry-run             # 只打印本次随机结果
/Python314/python.exe tools\hourly_remix.py --release-safe        # 开启授权过滤（仅对外发布时）
/Python314/python.exe tools\hourly_remix.py --sample-rate 96000   # 更高交付规格（96k/24bit）
/Python314/python.exe tools\hourly_remix.py --format mp3 --bitrate 320k  # 有损兜底
```

### 交付规格（2026-09-17 起，默认 WAV）

网易云等平台要求 **码率 > 320 kbps、采样率 > 44.1 kHz、单文件 < 200 MB**。
有损编码的上限就是 mp3 320 kbps，永远达不到「> 320 kbps」，因此**对外交付一律走无损**。

| 格式 | 采样率 | 位深 | 实测码率 | 120s 体积 | 备注 |
| --- | --- | --- | --- | --- | --- |
| **WAV（默认）** | 48 kHz | 24 bit | 2304 kbps | ≈ 33 MB | `pcm_s24le`，推荐对外交付 |
| WAV `--sample-rate 96000` | 96 kHz | 24 bit | 4608 kbps | ≈ 66 MB | 仍远低于 200MB 上限 |
| FLAC | 48 kHz | 24 bit | ≈ 885 kbps（压缩后） | ≈ 15 MB | 无损压缩，体积最小 |
| MP3 `--format mp3` | 48 kHz | 16 bit | 320 kbps | ≈ 5 MB | 兜底，**不满足 >320kbps** |

> ⚠️ 实现要点：pydub 无法真正持有 24-bit PCM——`AudioSegment.set_sample_width(3)`
> 会被**静默升为 32-bit**（实测）。因此 24-bit 只能靠导出时**显式指定 `pcm_s24le` 编码器**
> 走 ffmpeg 路径实现，详见 `main.py::_apply_delivery_spec`。

**随机层次（主路径 / 叠加层 / 进阶路径）**

| 层 | 开关 | 作用 |
| --- | --- | --- |
| 随机风格（主路径） | 默认开，无需开关 | `main.py --remix` 自带：phonk 风格随机选曲（bass/drum/guita/cowbell/synth 池）+ 随机偶数 BPM（110~150）+ 随机曲式模板。决定"选什么、多快、什么结构"。 |
| 混音师染色（叠加层，可选） | `--mixer-style`（默认 `none`；`random` 随机一位） | 24 位混音师签名总线 + 母带链。只影响音色/响度，不影响选曲。 |
| 跨类融合（进阶路径，可选） | `--fusion` | music 提示词链 + 跨类融合（随机混搭两类、乐器/情绪去重）→ 映射为具体素材轨。声学更丰富，但属复杂实现，默认不走。 |

**发布安全（默认关）**：`--release-safe` 显式开启时只用各池 manifest 中 `license_tier ∈ {free, pack}` 的
素材，restricted/unknown 一律剔除，满足网易云等平台对外发布要求。**默认关闭**，全素材池参与，避免内容过于单调；自用或确认授权后再开。

- **时长控制**：`bars = round(target_sec * bpm / 240)`（4 拍/小节）；BPM 从风格区间取偶数 →
  `bars = bpm/2`，理论时长精确 120.0s（实测偏差 <0.1s）。
- **防单调**：曲式模板与混音师默认避开最近 3 次用过的（`--no-repeat`）。
- **产物**：`output/hourly/<时间戳>_remix_<bpm>bpm_<bars>bars_<结构>[_<mixer>].wav`（`--fusion` 模式为 `_fusion_<风格>_...`），
  另维护 `hourly_index.json`（逐首元数据：`duration_ok` / bpm / 风格 / 种子 / 耗时 / `delivery` / `delivery_ok`）、
  `playlist.m3u8`、`hourly_remix.log`。
- **端到端校验**：导出后用 ffprobe 复核真实时长，偏差 > `--tolerance`（默认 3s）记 WARN；
  混音失败自动换种子重试（默认 3 次）。
- **交付规格校验**：导出后回读 codec / 采样率 / 位深 / 实测码率 / 体积写入 `delivery` 字段，
  只有 「码率>320kbps 且 采样率>44100Hz 且 体积<`--max-size-mb`(默认200) 且 时长在容差内」时
  `delivery_ok=true`；不满足则在 stdout 打 `DELIVERY=FAIL` 并列出原因。
- **环境**：`/Python314`（pydub + numpy + scipy + soundfile + audioop-lts），
  ffmpeg/ffprobe 用 `remix/bin` 内置版，无需系统 PATH。实测单首耗时约 22s。

## 编排配方持久化（recipe，2026-09-17 起）

每次渲染都把「这次到底用了什么」完整写进索引的 `recipe` 字段。起因：重渲历史产物时，
早期 genre 流水线的条目虽存了 `seed` / `tracks`，仍无法复现（与原型仅 r=0.09）——
**配方没记全，事后无从归因**。

`recipe` 覆盖（`main.py::build_recipe`）：

| 段 | 内容 |
| --- | --- |
| `engine` | `remix_version` + `main.py` / `templates/structures.json` / `mixer_styles.py` 的 sha256 |
| `inputs` | count / seed / bpm / bars / structure / release_safe / mixer_style / 传入的 tracks |
| `structure` | 模板原名 + **模板原文** + 解析后的 sections + fade_out_bars |
| `tracks` | **实际选中的每条素材**（相对 `MUSICKIT_ROOT` 的路径）、role、`gain_db`、`start_bar`/`end_bar`、变体周期、增益曲线摘要（sha1+极值） |
| `constants` | `ROLE_GAIN` / `VARIANT_EVERY` 当时的取值 |
| `mixer` | slug / name / `target_lufs` / 实际用到的总线 |
| `output` | 峰值 dBFS、格式、采样率、位深、编码器、时长 |

`recipe_digest` = 只覆盖「影响声音」的部分（忽略引擎指纹与输出路径）的 sha256，便于快速比对。

**内容指纹**：每次导出同时记 `fingerprints`（文件 sha256 + **跨编码稳定的包络指纹**
`envelope_hash`）。有了它，日后重渲可以直接和上一版已核验产物比对，不必再依赖原始文件
（原始文件常被改名/移动）。

> ⚠️ 教训（2026-09-17）：`rerender_from_index.py --no-resume` 曾把索引里其余记录清空
> （28 条实测数据被覆盖，靠 `rerender.log` + 磁盘产物 + 源索引才重建回来）。
> 现已修正：`--no-resume` 只表示「不跳过已存在的产物」，且写入带**收缩保护**——
> 条目数变少时先留 `release_index.json.bak`。

## 历史产物重渲为发布级 WAV（tools/rerender_from_index.py）

`hourly_remix.py` 在 2026-09-17 21:44 之前产出的都是 **128 kbps mp3**，不满足发布要求；
mp3 → wav 只会得到「假无损」（内容已不可逆丢失）。正确做法是用 `hourly_index.json` 里
已存的 `seed / bpm / bars / structure / mixer_style / tracks` **重新渲染**（同种子同参数可逐字节复现）。

```bash
/Python314/python.exe tools\rerender_from_index.py --dry-run       # 只列计划（30 首）
/Python314/python.exe tools\rerender_from_index.py --limit 1       # 先试 1 首
/Python314/python.exe tools\rerender_from_index.py                 # 全量（默认断点续跑）
/Python314/python.exe tools\rerender_from_index.py --only-seed 42  # 只重渲指定 seed
/Python314/python.exe tools\rerender_from_index.py --backfill-fingerprints  # 只补记指纹，不渲染
```

- 输出到 `output/release/`，命名保持原文件名（改成 `.wav`）便于溯源，另写 `release_index.json` + `rerender.log`。
- **不做任何随机**：`structure` / `mixer_style` / `bpm` / `bars` 全部取自索引，不过 `pick_excluding` 随机层。
- **优先按 `recipe.tracks` 复现**（新格式，含相对路径，最精确）；回退旧的 `tracks`（`cat:basename`）；
  都没有才交给 seed 随机。任一轨解析不到就退回随机并在日志说明（宁可退随机也不错配素材）。
- 渲染后逐层比对配方（选曲 / 编排 / 增益 / 结构 / 混音师 / 常量 / 引擎），
  日志形如 `配方: 选曲= 编排= 增益≠ 结构= 混音师= 常量= 引擎=`，一眼看出**哪一层变了**。
- 标了 `excluded_from_release` 的源条目会被跳过（防止已判定不可复现的条目被重新唤起）。
- 增量落盘 + `--no-resume` 强制重渲（**不会清空索引**）；单首约 40s、33 MB。

## 重渲保真度核验（tools/verify_release_fidelity.py）

历史 mp3 被外部进程批量改名（`loop/loop (N).mp3`、`ambient/ambient (N).mp3`、`.archived/`），
索引里的 `path` 已失效，**按文件名对不上**。因此改用**内容比对**：

```bash
/Python314/python.exe tools\verify_release_fidelity.py --patch-index
```

- 把两份音频解码为 8 kHz 单声道，取 10 ms 窗 RMS 包络算 Pearson r；同一编排 ≈ 0.999，不同内容明显偏低。
- 附带**双向唯一性**判据：每首重渲只能匹配到互不重复的原文件 —— 排除"都撞到同一首"的假阳性。
- `--patch-index` 把 `fidelity_match` / `reproduced` 写回 `release_index.json`。
- 实测（2026-09-17）：**29/29 复现成功**，r ∈ [0.99807, 0.99899]，双向唯一（1 首早期 genre
  流水线产物无法复现，已按用户指令删除，并标记 `excluded_from_release`）。

## 功能列表

| 功能 | 说明 |
| --- | --- |
| 多轨混音 | 同时叠加多轨或交叉淡化串联 |
| 分轨增益 | 每轨独立 dB 增益 |
| 削波 | 硬削波（截断）/ 软削波（tanh 饱和） |
| 归一化 | 峰值归一化 / RMS 归一化 |
| 淡入淡出 | 整体首尾淡变 |
| 交叉淡化 | 轨间 equal-power 交叉淡化（串联模式） |
| 动态压缩 | 压缩动态范围 |
| 高通/低通 | 滤波截止频率可调 |
| phonk beat 混音 | loop 切片 + 小节编排 + 内容去重，输出固定小节数（`--bars`/`--bpm`） |
| 骨架保底选音 | drum/bass/guita 强制选取 >=1 小节 loop/stem 并强制循环层 |
| 发布安全模式 | --release-safe 仅用 free/pack 授权素材（license_tier 过滤） |
| 防覆盖命名 | 输出文件名同秒冲突自动递增（_1/_2） |
| 混音师风格着色 | --mixer-style：24 位混音师分轨总线链 + 风格母带（共享 burbidge_album/mixer_styles.py） |
| 混音师电台 | tools/mixer_radio.py：固定签名 × 随机流派连续产出（m3u8 + 报告） |
| 混音师流服务 | tools/mixer_stream.py：本地无限流（/api/channels /api/stream/<slug> /api/track/<slug>） |
| 每小时自动混音 | tools/hourly_remix.py：随机风格 × 固定 2 分钟，索引/播放列表/日志 + 时长校验 |

## 项目结构

```
remix/
├── main.py                 # 程序入口 + 依赖检查 + 随机混音 CLI（--mixer-style 混音师风格）
├── core/
│   ├── audio_loader.py     # 加载 / 参数统一 / 导出
│   ├── audio_mixer.py      # 混音引擎（纯业务逻辑，零 GUI 依赖）
│   └── loop_slicer.py      # BPM 网格切片 / 曲式编排 / 内容判重
├── gui/
│   └── main_window.py      # tkinter 主界面（仅音频混音）
├── templates/
│   └── structures.json     # 曲式模板库（classic_drop / ambient_ghost / loop_stack）
├── tools/
│   ├── mixer_radio.py      # 本地混音师电台（MUBERT_COMPARISON.md L2）
│   ├── mixer_stream.py     # 本地混音师无限流服务（L3）
│   ├── hourly_remix.py     # 每小时随机风格混音驱动（固定 2 分钟 + 索引/播放列表/日志）
│   ├── rerender_from_index.py      # 按索引参数复现历史混音为发布级 WAV
│   ├── verify_release_fidelity.py  # 内容比对核验重渲保真度（包络相关 + 双向唯一）
│   ├── audio_fingerprint.py        # 跨编码内容指纹（envelope_hash / sha256），供上述两者共用
│   └── ...                 # 采样入库/审计/查重等治理脚本
├── utils/
│   └── progress_reporter.py# 线程安全进度报告
└── tests/                  # pytest 测试套件（含 main.py 选音逻辑 / --release-safe 覆盖）
```

## 测试

```bash
pip install pytest
pytest tests/ -q              # 全量
pytest tests/ -q -m smoke     # 快速冒烟档（纯逻辑用例，无 ffmpeg 编解码）
```

> 注：涉及 GUI 的进度报告测试在缺少 tkinter / Tcl 环境时会自动跳过（skip），
> 不会失败。

---

## 提示词驱动混音（来自 `<仓库根>/music/`，已整合进本项目）

本引擎可被 **`<仓库根>/music/prompt_driven_remix.py`** 以「提示词」驱动：
`music_prompt_generator` 生成的结构化提示词（乐器 / BPM / 情绪）经该桥接器映射为本引擎的
`run_remix(tracks, bpm, structure)`，从而用真实素材产出混音。

- 提示词里的 `instruments` → 经 `<仓库根>/instrument_taxonomy.json` 规范分类体系映射
  （music 工具 242 个乐器词 → 37 个规范类目 → musickit 池），**避免把不同乐器家族压进粗池**。
  - 真人 **acapella 池**（`<仓库根>/acapella`，Coollider Acapellas）按 `vocal` 角色接入；
  - 动物叫声已独立为 **animal 池**（`<仓库根>/animal`），不再冒充人声；
  - 钢琴/弦乐/铜管/笛箫/民族乐器等 musickit 无样本的类目会被跳过并记入 `gaps`，绝不假映射。
- `bpm` → 混音目标速度
- `moods` / `subgenre` → 曲式模板（`classic_drop` / `ambient_ghost` / `loop_stack`）

运行桥接器需 `/Python314`（pydub + numpy + audioop-lts + scipy + soundfile），并把
`MUSICKIT_ROOT` 指向 `<仓库根>`（桥接器已默认设置）。详见 `<仓库根>/music/prompt_driven_remix.py`。
桥接器同样支持 `--mixer-style`（slug 或 random，random 时每条提示词配一位随机混音师，
所用混音师写入 --report 的 mixer_style 字段）。
