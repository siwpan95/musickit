# 新人开发上手指南 · musickit

> **本文定位**：面向**第一次接触本仓库**的开发者。你不需要读过 README，
> 照着本文从零跑起来，就能混出一首成品音频、跑通测试、提交你的第一笔改动。
>
> **本文口径**：所有命令与数字均为 **2026-11-02 在 Windows / CPython 3.13+ 环境实测**得出。
> 仓库自 2026-11-02 起改用「代码入库、素材不入库」模式（见 [§2](#2-代码获取)），
> 这是新人最大的认知落差，本文档第一优先讲清楚。
>
> **配套文档**：功能全貌见 [README.md](README.md)；两条管线打通关系见
> [INTEGRATION.md](INTEGRATION.md)；素材调性体系见 README「调性标注与 `--key`」。

---

## 目录

| # | 章节 | 你将获得 |
|---|------|---------|
| 0 | [30 秒速览](#0-30-秒速览) | 心智模型：仓库是干什么的、哪些东西不在仓库里 |
| 1 | [环境准备](#1-环境准备) | Python / ffmpeg / 虚拟环境就绪 |
| 2 | [代码获取](#2-代码获取) | 拿到代码，并认清「素材不在仓库里」 |
| 3 | [首次验证](#3-首次验证) | 3 条命令确认环境无误 |
| 4 | [准备素材](#4-准备素材) | 让引擎真的有音频可混 |
| 5 | [启动各模块](#5-启动各模块) | 混音引擎 / 提示词 / 电台 / 混音师流 |
| 6 | [常见问题](#6-常见问题-faq) | 12 个实测踩过的坑与解法 |
| 7 | [开发工作流](#7-开发工作流) | 分支、提交、测试、推送 |
| 8 | [仓库约定速查](#8-仓库约定速查) | 不可违反的硬规则 |
| 9 | [模板化说明](#9-模板化说明) | 如何把本文复用到其它仓库 |

---

## 0. 30 秒速览

### 这个仓库是什么

**musickit** 是一个**本地 phonk 音乐流水线**：把真实采样素材（鼓 / 贝斯 / 牛铃 / 人声…）
按 phonk 的曲式结构自动混成成品音频，并可开成 24/7 网络电台。

```
        素材池（13 个乐器池，音频不入库）
                    │
                    ▼
   ┌────────────────┴────────────────┐
   │                                 │
music/ 风格提示词生成器        remix/ 混音引擎
（63 流派风格池 → 结构化提示词）  （选音 → 切 loop → 编排 → 混音 → 母带）
   │                                 │
   └──────── music/prompt_driven_remix.py（桥接器）────────┘
                    │
                    ▼
              burbidge_album/  24 位混音师签名链
                    │
                    ▼
              radio/  24/7 网络电台（Flask）
```

### 你必须先知道的三件事

| 事实 | 影响 |
|------|------|
| **素材音频与 ffmpeg 二进制都不在版本库里** | 新克隆的 13 个素材池是**空的**（只有 `manifest.json`）。不补素材，混音会直接报错 |
| **代码仓库很轻** | 干净克隆约 **30 MB**，几十秒完成；30 GB 的素材在版本库之外 |
| **素材全为公共领域（Public Domain）** | 可自由用于制作与发布，无需署名。原 `--release-safe` 过滤已废弃（2026-11-02） |

> **最容易踩的认知落差**：新人看到 `drum/manifest.json` 里有 4001 条记录，
> 以为音频文件也在，结果一跑就报「未找到任何音频素材」。
> 正确顺序永远是：**先装依赖 → 再确认环境 → 最后补素材**（本文 §1 → §3 → §4）。

---

## 1. 环境准备

### 1.1 Python

| 项 | 要求 | 说明 |
|----|------|------|
| 版本 | **CPython 3.9 ~ 3.14** | 3.13+ 需额外装 `audioop-lts`（见下）；3.14 已实测通过 |
| 类型 | 标准 CPython | 本项目**不依赖** conda；用 `venv` 即可 |

**为什么 3.13+ 要装 `audioop-lts`**：Python 3.13 按 PEP 594 移除了标准库 `audioop`
模块（`aifc`/`sunau`/`chunk` 等一并移除），而 `pydub` 几乎每个操作都 import 它。
`audioop-lts` 是该模块的 LTS 复刻版（PSF-2.0 许可），是官方推荐的替代方案：

```bash
pip install audioop-lts
```

若漏装，报错是 `ModuleNotFoundError: No module named 'audioop'`。

### 1.2 ffmpeg / ffprobe

`pydub` 只是 ffmpeg 的封装，**没有 ffmpeg 二进制，混音无法运行**。

解析顺序由 `remix/core/binfind.py` 统一约定（**重要**）：

```
1. remix/bin/ffmpeg.exe        ← 项目自带，优先（锁定版本）
2. 系统 PATH 中的 ffmpeg        ← 兜底
3. 都没有 → 报 BinaryNotFound，提示具体路径与安装方式
```

**两种安装方式，任选其一：**

```bash
# 方式 A：放进 remix/bin/（项目自带，版本锁定，跨机一致）
#   从 https://ffmpeg.org/download.html 下载 Windows build（gyan.dev 的 essentials build 即可）
#   解压后把 ffmpeg.exe 与 ffprobe.exe 复制进 remix/bin/

# 方式 B：装到系统 PATH
winget install ffmpeg          # Windows
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Debian / Ubuntu
```

> ⚠️ **`.gitignore` 排除了 `remix/bin/*.exe`**，所以方式 A 的文件**不会**随 clone 到达。
> 换机器或新克隆后都要重新放一次。这是「仓库能跑但我的机器不能跑」的头号原因。

### 1.3 虚拟环境

**路径务必用纯英文、无空格**。Windows 控制台默认 GBK 编码，
中文路径会导致 `pip install` 报 `UnicodeDecodeError` 或 `OSError: [Errno 22]`。

```bash
# 在仓库根目录执行
python -m venv .venv

# Windows CMD
.venv\Scripts\activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate
```

> PowerShell 若报「禁止运行脚本」，改用 CMD 的 `activate.bat`；
> 或执行 `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`（**不要**用 `Bypass`/`Unrestricted`）。

### 1.4 安装依赖

仓库提供**四份依赖清单**，按需选：

| 清单 | 内容 | 何时用 |
|------|------|--------|
| `requirements.txt` | 仓库级聚合（混音引擎 + 桥接器 + pytest） | **默认选这个** |
| `remix/requirements.txt` | 仅混音引擎（pydub / numpy / scipy / soundfile / audioop-lts） | 不想装测试依赖 |
| `radio/requirements.txt` | 仅电台（Flask / waitress / mutagen / requests） | 只跑电台 |
| `requirements.lock.txt` | 全仓**精确版本**锁定（`==`） | 需要与他人完全一致的环境 |

```bash
# 推荐：仓库级聚合
pip install -r requirements.txt

# 需要完全复现（CI / 协作排查）
pip install -r requirements.lock.txt
```

可选依赖：

```bash
pip install -r remix/requirements-keys.txt   # librosa，用于素材调性标注（较重）
```

**验证依赖装好**：

```bash
python -c "import pydub, audioop, numpy, scipy, soundfile; print('deps OK')"
```

### 1.5 环境准备检查表

- [ ] Python ≥ 3.9（3.13+ 已装 `audioop-lts`）
- [ ] `ffmpeg` + `ffprobe` 可用（`remix/bin/` 或系统 PATH）
- [ ] 虚拟环境已激活
- [ ] 仓库路径纯英文无空格
- [ ] `pip install -r requirements.txt` 完成

---

## 2. 代码获取

```bash
git clone https://gitee.com/siwpan/musickit.git
cd musickit
```

**镜像仓库**（GitHub，与 Gitee 同步）：

```bash
git clone git@github.com:siwpan95/musickit.git
```

配置双远端（推荐）：

```bash
git remote add github git@github.com:siwpan95/musickit.git
git fetch --all
```

> **只想要最新代码、不需要历史**：`git clone --depth 1 https://gitee.com/siwpan/musickit.git`
> 可省下大量历史拉取时间。

### 克隆后你会看到什么

```
musickit/
├── bass/  drum/  guita/  cowbell/  synth/  sfx/  acapella/
├── animal/  keys/  strings/  brass/  woodwind/  ethnic/
│   └── 每个目录里只有 manifest.json —— 音频不在仓库里
├── remix/        # 混音引擎（main.py + core/ + gui/ + tools/ + tests/）
├── music/        # 风格提示词生成器（63 流派风格池）+ 桥接器
├── burbidge_album/  # 24 位混音师签名链
├── radio/        # 网络电台
├── instrument_taxonomy.json   # 242 乐器词 → 37 类目 → 13 池
└── scripts/ci_smoke.sh        # 一键自检 + 冒烟
```

**关键认知**：13 个素材池目录**只有 `manifest.json`**（登记了 30631 条素材的
文件名、时长、sha256、来源），音频文件本身被 `.gitignore` 排除。

| 目录 | 入库内容 | 不入库内容 |
|------|---------|-----------|
| `bass/` `drum/` `guita/` … | `manifest.json` | 全部 `.wav` 音频 |
| `remix/bin/` | `README.md` | `ffmpeg.exe` / `ffprobe.exe` |
| `remix/output/` `burbidge_album/album/` | — | 成品音频、渲染缓存 |
| `manifest_index.json` | — | 总索引（需自行重建） |

---

## 3. 首次验证

**三条命令，按顺序跑。** 前两条不依赖素材，第三条会告诉你缺什么。

### 3.1 环境自检

```bash
python remix/tools/doctor.py
```

正常输出（**已有素材的机器**）：

```
ffmpeg     : <仓库路径>\remix\bin\ffmpeg.exe
ffprobe    : <仓库路径>\remix\bin\ffprobe.exe

池           manifest      磁盘      缺失
bass             889      20     869
drum            4001      20    3981
keys            2675      10    2665
strings         2884      40    2844
...
合计             30631     372   30259
```

> 数字取自 2026-11-03 实测（仓库路径下已有部分素材）。`manifest` 列是**入库的索引条数**，
> 与机器无关（每个池的 `manifest.json` 都入库）；`磁盘` 列因人而异，取决于你本地恢复了多少素材。

**干净克隆**（**这是新人的预期状态，不是故障**）：

```
⚠️ 告警：
   - 素材池为空（manifest 记着 30631 条，磁盘 0 个文件）—— 干净克隆下的预期状态；要渲染需先恢复素材

退出码 1（0=通过 / 1=告警 / 2=硬失败）
```

> **退出码语义**：`0` 全部通过 · `1` 有告警（如素材缺失）· `2` 硬失败（ffmpeg 缺失 / 测试失败）。
> 新人看到退出码 1 先别慌 —— 素材缺失在干净克隆下**必然**发生。

### 3.2 冒烟测试（不需要任何素材）

```bash
bash scripts/ci_smoke.sh
```

Windows 需 Git Bash；或用 WSL：

```bash
PYTHON=/path/to/python bash scripts/ci_smoke.sh
```

实测输出（干净克隆，2026-11-02）：

```
== 文档数字一致性 ==
真实收集数：total=343  remix=285  music=58  smoke=221  smoke_music=36
✅ 文档数字与真实一致

== 编码门禁（文本模式 open 需显式 encoding） ==
✅ 文本模式 open() 均已显式指定 encoding（扫了 109 个 .py）

== pytest -m smoke ==
221 passed, 122 deselected in 3.92s

✅ 冒烟检查通过
```

> `pytest` 的 Tk 用例（`test_progress_reporter`）会**偶发** skip —— 本机 `tcl/tcl8.6/init.tcl`
> 明明在，初始化却偶尔失败。所以你看到的 `passed` 可能比上面少一条（220 而不是 221），
> **这是环境抖动不是故障**：门禁按**收集数**核对，不看 passed。

> **冒烟档（`-m smoke`）不碰 ffmpeg 编解码、不依赖真实素材**，秒级跑完。
> 这是你验证「代码环境没问题」的最快路径。

### 3.3 全量测试

```bash
python -m pytest remix/tests music/tests -q
```

实测：**343 用例**（收集数；偶发的 Tk 用例会 skip，所以 `passed` 可能少一条 —— 门禁按**收集数**核对）。

---

## 4. 准备素材

引擎需要真实音频才能渲染。素材**不入库**，需自行获取。

### 4.1 方案 A：抓取公共领域音乐（推荐，公版可商用）

仓库自带两个脚本，已于 2026-11-02 实测走通全链路：

```bash
# 1) 抓公版整曲（CC0，免注册直下）
python remix/tools/fetch_freepd.py --out D:/tmp/freepd_src --limit 4
python remix/tools/fetch_freepd.py --out D:/tmp/freepd_src --list    # 只列出不下载

# 2) 归一化 → demucs 分离四轨 → 分池落盘 + 更新 manifest
python remix/tools/ingest_stems.py --src D:/tmp/freepd_src --source-tag freepd

# 只看计划不落盘
python remix/tools/ingest_stems.py --src D:/tmp/freepd_src --dry-run

# 按来源标签整批撤回（后悔药）
python remix/tools/ingest_stems.py --purge-tag freepd --dry-run
python remix/tools/ingest_stems.py --purge-tag freepd
```

**stem 映射**（demucs htdemucs 四轨）：

| demucs 输出 | musickit 池 | 用途 |
|-------------|------------|------|
| `drums.wav` | `drum/` | 鼓 |
| `bass.wav` | `bass/` | 贝斯 |
| `other.wav` | `guita/` | 旋律/其他（项目约定 other 即吉他轨） |
| `vocals.wav` | `acapella/` | 人声 |

**依赖**：`torch` + `demucs`。用 `--python` 指定装有它们的解释器：

```bash
python remix/tools/ingest_stems.py --src D:/tmp/freepd_src --python /e/Python314/python.exe
```

**成本参考**：CPU 分离约 **1.2× 实时**（240 秒曲 ≈ 3.3 分钟/首）。

> ⚠️ **demucs 对 mp3 的兼容性坑**：demucs 自带加载器对部分 mp3 流会报
> `malformed stream: mpa: invalid main_data offset`。脚本已内置解法 ——
> 输入先用 ffmpeg 归一化为 44.1k/2ch/16bit WAV 再送 demucs。

### 4.2 方案 B：从已有素材库复制

若你本机/同事已有素材库，**直接整目录复制**即可（每个池目录含音频 + `manifest.json`）：

```bash
# 从素材库复制到本仓（Windows 示例）
cp -r /path/to/musickit/bass/.  ./bass/
cp -r /path/to/musickit/drum/.  ./drum/
# …其余池同理
```

复制后校验一致性：

```bash
python remix/tools/doctor.py --hash 200
```

`--hash 200` 会抽样 200 个文件重算 sha256，与 manifest 记录比对，
报告「哈希不符」的比例 —— 用于确认素材没被改动过。

### 4.3 素材来源参考

| 站点 | 内容 | 说明 |
|------|------|------|
| <https://freepd.cn/music> | FreePD 中文镜像 · 公共领域 | 免注册直下，适合做 stem 源 |
| <https://freepd.com> | FreePD 原站（CC0） | 经典/氛围/电子分类齐全 |
| <https://mixkit.co/free-stock-music> | Mixkit 免费音乐 | 免费商用，无需署名 |
| <https://freesound.org> | Freesound（按 CC0 筛选） | one-shot / 环境音最全 |

### 4.4 授权说明（重要）

> **`--release-safe` 已于 2026-11-02 废弃**。该开关原按 manifest 的 `license_tier` 过滤，
> 但该字段严重失真（30259 条中 `unknown` 占 64.7%、`restricted` 仅 3.6%），
> 而实际素材全为公版。过滤只放行 31.7% 的素材，等于无谓砍掉 68.3%。
>
> **现状**：参数仍接受（兼容旧脚本），但**不做任何过滤**，也不再输出剔除日志。
> 历史字段 `license_tier` 保留在 manifest 中，仅作溯源参考，不参与任何判定。
>
> 相关脚本 `remix/tools/tag_license_tiers.py`、`audit_licenses.py` 仅作历史参考。

### 4.5 调性标注（可选）

给素材标调性，混音时按调性择音，避免调性打架：

```bash
python remix/tools/detect_keys.py               # 只补缺 key 的
python remix/tools/detect_keys.py --force       # 全部重算
python remix/tools/detect_keys.py --pools bass guita --dry-run
```

需先装 `remix/requirements-keys.txt`（librosa）。混音时指定目标调性：

```bash
python remix/main.py --remix --key Am       # 完整调性
python remix/main.py --remix --key 小调     # 只给调式（无主音）
```

> ⚠️ **单音素材别信 chroma**：`detect_keys` 用 librosa 估调，实测 `Piano.ff.B5` 被判成 **C#m**
> （conf 仅 0.38 / margin 0.05）—— 高音区泛音把音级带偏了。所以 `fetch_iowa_mis.py` 抓来的单音
> 走**文件名音级**（`key_pitch_only`），选音时按 `musical_key.rank_pitch()` 只比音级比较。

### 4.6 素材从哪来（把空池填起来）

干净克隆里 13 个池只有 `manifest.json`，音频不在库里。要真正跑起来，得先灌素材。
两条已验证可用的路：

```bash
# ① 整曲 → stem（demucs 分离成 bass/drum/guita/acapella）
python remix/tools/fetch_freepd.py --out D:/tmp/src --limit 4
python remix/tools/ingest_stems.py --src D:/tmp/src --source-tag freepd

# ② 乐器单音（一次覆盖 keys/strings/brass/woodwind 四池）
python remix/tools/fetch_iowa_mis.py --limit 2 --dry-run     # 先看计划
python remix/tools/fetch_iowa_mis.py --instruments piano violin trumpet flute --limit 10
```

② 用的是爱荷华大学乐器采样库（MIS），站点声明「可自由用于任何项目、无限制」，内容是**每音一条单音
one-shot**。实测灌入 137 条（13 件乐器各 10 条），全部 44.1kHz/16bit，manifest 记来源/授权原文/直链/sha256。

> **ethnic（民族乐器）没有可用的公版源**：FreePats 的 ethnic 目录只有卡林巴/口弦琴，
> 二胡/古筝/笛子/唢呐这类不存在；archive.org 与 GitHub 在本机不可达。这一池目前只能手工补。

---

## 5. 启动各模块

> 以下命令中 `python` 指**已激活虚拟环境**的解释器。Windows 若激活失败，
> 可直接用 `.venv\Scripts\python.exe` 替代。

### 5.1 混音引擎（核心）

```bash
# 图形界面（tkinter）
python remix/main.py

# 命令行随机混音（phonk 骨架：drum + bass + guita）
python remix/main.py --remix
```

**常用参数**：

```bash
python remix/main.py --remix --count 5 --bars 64 --bpm 140 --format wav
python remix/main.py --remix --structure classic_drop --seed 42 --out output
python remix/main.py --remix --mixer-style wallace       # 24 位混音师风格着色
python remix/main.py --remix --key Am                    # 按调性择音
```

| 参数 | 含义 |
|------|------|
| `--remix` | 启用命令行随机混音模式 |
| `--count N` | 音轨数（默认 3 = phonk 最小骨架；典型 4~6） |
| `--bars N` | 小节数（默认 32；>12 时按 intro→drop→outro 编排） |
| `--bpm N` | 速度（默认随机 110~150） |
| `--seed N` | 随机种子，**固定后结果完全可复现** |
| `--structure S` | 曲式模板（`classic_drop` / `ambient_ghost` / `loop_stack` …） |
| `--format F` | `wav`（默认）/ `mp3` / `ogg` / `flac` |
| `--out DIR` | 输出目录（默认 `remix/output/`） |
| `--mixer-style S` | 混音师签名（24 位 slug 或 `random`） |
| `--key K` | 目标调性（完整调性或调式名） |

**输出位置**：`remix/output/`（已被 `.gitignore` 排除，不会误提交）。
同名冲突自动递增 `_1` / `_2`，**不覆盖**旧产物。

**交付规格**（2026-09-17 起生效，面向网易云音乐等平台）：
WAV / 48 kHz / 24 bit / 立体声 ≈ 2304 kbps，单文件 < 200 MB。
有损格式统一给到 320 kbps 上限。

**实测样例**：

```
[remix] 曲式模板：ambient_ghost（氛围幽灵：旋律+垫底先行，鼓后半才进…）
[remix] BPM=150，共 16 小节（25.6s），已选择 3 条音轨（phonk 风格）：
  1. [drum] drum (527).wav (3.6s)
  2. [bass] bass (3800).wav (102.7s)
  3. [guita] guita (271).wav (2.0s)
[remix] 交付规格：WAV 48000Hz / 24bit / 2ch ≈ 2304 kbps
[remix] 混音完成（25.6s，150BPM x 16 小节），已保存至：…\phonk_remix_20261102_212151.wav
```

### 5.2 风格提示词生成器

```bash
python music/music_prompt_generator.py --list           # 列出 63 个风格分类
python music/music_prompt_generator.py -c phonk          # 生成指定风格
python music/music_prompt_generator.py -n 20 --seed 42 --export json
python music/music_prompt_generator.py --fusion          # 跨类融合
```

**图形界面**（tkinter）：`python music/music_prompt_gui.py`，或运行 `music/运行GUI.bat`。

**风格池自检**：

```bash
python music/validate_styles.py --strict
```

### 5.3 提示词驱动混音（桥接器）

把提示词经 `instrument_taxonomy.json`（242 乐器词 → 37 类目）映射为引擎调用：

```bash
python music/prompt_driven_remix.py -c phonk --mixer-style mikedean
python music/prompt_driven_remix.py -n 3 --fusion --mixer-style random --seed 42
python music/prompt_driven_remix.py --prompt-json p.json --mixer-style burbidge
```

### 5.4 混音师流服务（24 频道）

```bash
python remix/tools/mixer_stream.py --port 8010
```

| 端点 | 用途 |
|------|------|
| `/api/channels` | 频道目录（24 位混音师，含名称、风格标签、配色） |
| `/api/stream/<slug>` | 无限流（浏览器 / VLC 即点即播，首曲约 15~25 秒起播） |
| `/api/track/<slug>?seed=N&bars=32` | 单曲生成并下载 |

本地电台（输出 m3u8 播放列表）：

```bash
python remix/tools/mixer_radio.py --channel wallace --count 3
```

### 5.5 网络电台（Flask）

```bash
python radio/run.py                 # 只起本地服务
python radio/run.py --expose        # 起服务 + 自动 cloudflared 公网穿透
python radio/run.py --expose ngrok  # 用 ngrok（需先配 authtoken）
```

| 地址 | 用途 |
|------|------|
| <http://localhost:8000/> | 控制面板 |
| <http://localhost:8000/stream> | 直接收听 |
| <http://localhost:8000/hls/live.m3u8> | HLS 原生收听（Safari / iOS / Android） |
| <http://localhost:8000/api/health> | 健康检查 |

> **端口固定为 8000**（定义在 `radio/radio/config.py` 的 `HTTP_PORT`）。
> 端口被占用时报错是**误导性的** `PermissionError: [WinError 10013]`，
> 实际含义是「端口已被别的进程占用」，详见 [§6.3](#63-电台起不来-winerror-10013)。

### 5.6 固定风格专辑（24 位混音师）

```bash
python burbidge_album/build_album.py              # 全量 24 位
python burbidge_album/build_album.py wallace      # 增量：只做某一位
```

产物：`burbidge_album/album/<slug>/`（成品 + 试听页）、`album/channels.json`（频道目录）。

---

## 6. 常见问题（FAQ）

> 以下每一条都是**实测复现**过的，不是推测。

### 6.1 跑混音报「未找到任何音频素材」

```
FileNotFoundError: 在 <路径> 下未找到任何音频素材
（请确认 bass / drum / guita / cowbell / synth 目录中存在音频文件）。
```

**原因**：干净克隆的素材池是空的（音频不入库）。

**解法**：按 [§4](#4-准备素材) 补素材，然后：

```bash
python remix/tools/doctor.py     # 确认磁盘文件数 > 0
```

### 6.2 `ModuleNotFoundError: No module named 'audioop'`

**原因**：Python ≥ 3.13 移除了标准库 `audioop`，而 `pydub` 依赖它。

**解法**：

```bash
pip install audioop-lts
```

### 6.3 电台起不来：`WinError 10013`

```
PermissionError: [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。
```

**原因**：**不是权限问题** —— 是 8000 端口已被占用（Windows 对「端口已占用」报 10013，
而不是 Linux 的 `EADDRINUSE`，非常误导）。

**解法**：

```bash
# 查占用
netstat -ano | findstr :8000
# 改端口（编辑 radio/radio/config.py 的 HTTP_PORT）
```

> 实测：改 `HTTP_PORT = 8123` 后电台立即正常启动，控制面板返回 HTTP 200。

### 6.4 `pip install` 报 `UnicodeDecodeError` / `OSError: [Errno 22]`

**原因**：项目或虚拟环境路径含中文 / 空格。Windows 控制台默认 GBK 编码，
与 pip 内部的 UTF-8 冲突。

**解法**：把仓库和虚拟环境都放在**纯英文无空格**路径下（如 `D:\repos\musickit`）。
这是硬性约定，不是洁癖。

### 6.5 `RuntimeWarning: Couldn't find ffmpeg or avconv`

**原因**：`remix/bin/` 没有二进制，且系统 PATH 也没有。

**解法**：见 [§1.2](#12-ffmpeg--ffprobe)。注意 `.gitignore` 排除了 `remix/bin/*.exe`，
**换机器后必须重新放一次**。

### 6.6 `doctor.py` 退出码 1，是不是坏了？

**不是。** 退出码语义：`0` 通过 / `1` **告警** / `2` 硬失败。
干净克隆下素材必然缺失，退出码 1 是**预期状态**。
真正该警觉的是退出码 **2**（ffmpeg 缺失或冒烟测试失败）。

### 6.7 素材池「缺失 20 条」「缺失 115 条」

**原因**：manifest 登记的条目在磁盘上找不到对应文件 —— 通常是历史归档、
或素材被手动移动过。

**判定**：这**不影响**渲染（引擎只用磁盘上真实存在的文件），
只是 manifest 与磁盘有偏差。`doctor.py` 的哈希检查（`--hash 200`）可确认素材内容是否被改动。

### 6.8 `--key Am` 输出一堆「未知」，调性择音没生效

```
[remix] 目标调性 A minor：兼容候选 0 条（同调 0 / 关系调 0 / 五度 0），主音不同 0，
        不兼容 0，未知 8239｜7 个池无兼容素材已放宽
```

**原因**：调性信息来自 manifest 的 `key` 字段，而该字段需要**先跑标注工具**才有值。
素材刚入库时 `key` 是空的，于是全部落进「未知」档。

**解法**：先标注，再混音：

```bash
python remix/tools/detect_keys.py            # 写回 manifest 的 key 字段
python remix/main.py --remix --key Am         # 此时才有兼容候选计数
```

> 注意：`--key` 的设计是**只重排、不删除**。池子里没有兼容素材时会放宽到全池，
> 并在日志里报「N 个池无兼容素材已放宽」—— 不会因为调性筛不出音而失败。

### 6.9 混音结果每次都不一样，怎么复现？

**用 `--seed`**。固定种子后选音、曲式、编排全部可复现：

```bash
python remix/main.py --remix --seed 42 --bars 16
```

同一组合 (`--seed` + `--bars` + `--bpm` + `--count` + `--structure`) 必得同一结果。

### 6.10 找不到 `main.py`，或 `import core` 失败

**原因**：从仓库根目录之外调用了 `remix/main.py` 相对路径。

**解法**：在 `remix/` 目录下运行，或用仓库根的相对路径：

```bash
python remix/main.py --remix
```

脚本自身会把所在目录插入 `sys.path`，但**素材根**是独立的：
它默认取 `main.py` 的**上级目录**，或读环境变量 `MUSICKIT_ROOT`：

```bash
MUSICKIT_ROOT=/path/to/musickit python remix/main.py --remix
```

### 6.11 GUI 启动失败 / 没有窗口

**原因**：tkinter 未随解释器安装（精简版 Python 常见）。

**解法**：用官方安装包，或直接用命令行模式（`--remix`），它不依赖 tkinter。

### 6.12 输出文件没找到

**默认输出目录是 `remix/output/`**（相对 `main.py` 所在目录，不是当前工作目录）。
用 `--out` 显式指定，或看运行日志最后一行「已保存至：…」。

### 6.13 提交时想把素材一起推上去 —— 不要

`.gitignore` 已排除全部音频。**不要**用 `git add -f` 强行加入：
30 GB 音频会撑爆仓库历史，且违反仓库约定。

要改的只是 `manifest.json`（文件名 / 时长 / sha256 / 来源），它**是**入库的。

---

## 7. 开发工作流

### 7.1 分支

```bash
git checkout -b feature/your-topic
```

主分支是 `master`。**不在 `master` 上直接改**。

### 7.2 提交信息规范

仓库使用**结构化前缀**，从历史提交归纳：

```
<type>(<scope>): <一句话说明>
```

**type 取值**：`feat`（新功能）· `fix`（修 bug）· `docs`（文档）·
`chore`（杂务 / 构建 / gitignore）· `refactor`（重构）· `test`（测试）· `perf`（性能）

**scope 取值**：`remix` · `music` · `radio` · `build` · `paths` · `encoding` · `docs` · `deps` · `ci`

实例（取自本仓历史）：

```
feat(ci): 文档里写死的测试数字做成机械门禁
fix(env): PATH 前置改幂等；三个入库脚本从「导入即 NameError」修好
docs(paths): 去本地化 —— 全仓硬编码本机路径改为可推导 + 环境变量
refactor(boot): 抽 core/boot.py，把 main.py 的 5 种加载方式收敛成一个
```

### 7.3 提交前必跑

```bash
# 1) 自检 + 冒烟（一条命令走完）
bash scripts/ci_smoke.sh

# 2) 全量测试
python -m pytest remix/tests music/tests -q

# 3) 文档数字一致性门禁
python scripts/check_doc_counts.py

# 4) 编码门禁（文本模式 open 必须显式 encoding）
python scripts/check_encoding.py
```

**关于第 3 条**：仓库文档里写死的测试数字（如「**343 用例**」）由
`scripts/check_doc_counts.py` 做机械校验 —— 加了用例却忘了改文档会被它拦下。
`--fix` 可自动改正这两类数字。

**关于第 4 条**：Windows 上 `open()` 默认用 locale 编码（中文系统是 GBK），
写中文内容（中文路径 / 素材标题 / ID3 注释 / manifest 里的中文 license 文本）
会写出乱码或直接 `UnicodeEncodeError`。这类 bug 在 UTF-8 locale 的开发机上不复现，
所以由 `scripts/check_encoding.py` 做机械门禁：文本模式的 `open()` 缺 `encoding=`
就报错退出。**二进制模式不要加 `encoding=`**（那样本身就是非法用法）。

```bash
python scripts/check_doc_counts.py --fix
```

### 7.4 推送

```bash
git add -A
git commit -m "feat(remix): <你的说明>"
git push origin feature/your-topic
```

推后核对：

```bash
git ls-remote origin master     # 确认远端 SHA 与本地一致
```

> **推送纪律**：本地提交随时可做；**推送前请确认自己在场且明确放行**。
> 推送后必须用 `ls-remote` 核对，不能只看 `git push` 的输出 ——
> `push` 输出打印的 URL 可能是改名前的旧地址，容易误判。

---

## 8. 仓库约定速查

**以下是硬规则，违反会被 review 打回。**

| # | 约定 | 说明 |
|---|------|------|
| 1 | **素材与二进制不入库** | 音频、`remix/bin/*.exe`、`manifest_index.json` 一律排除；只提交 `manifest.json` |
| 2 | **路径去本地化** | 活文档与配置**不写死盘符路径**；用环境变量推导或占位符（`<PATH>`）。新写代码同理 |
| 3 | **`archived/` 只进不出** | 垃圾桶/归档区：移动而非删除，不参与混音 |
| 4 | **文档数字必须与代码一致** | 由 `check_doc_counts.py` 门禁，不靠人记 |
| 5 | **生成物不提交** | `remix/output/`、`burbidge_album/album/`、`_stretch_cache/`、`TEST_REPORT.md` 均已排除 |
| 6 | **中文编码显式声明** | 脚本首行 `# -*- coding: utf-8 -*-`；读写中文文件用 `encoding="utf-8"`；由 `check_encoding.py` 门禁 |
| 7 | **文件名用 ASCII** | 避免 `新建文本文档.py` 这类中文文件名（本仓已因此踩坑并重命名） |
| 8 | **失败要说人话** | 错误信息要带**具体路径与操作建议**，不要抛裸 `[WinError 2]` |
| 9 | **合并前先同步** | `git fetch origin` 后确认无分叉再动手 |
| 10 | **许可与授权** | 仓库 MIT；素材全为公共领域，可商用，署名非必需 |

---

## 9. 模板化说明

本文是**可复用的上手指南模板**。要把同款文档用于其它仓库，按下表替换：

| 章节 | 通用做法 | 本仓实例 |
|------|---------|---------|
| §0 速览 | 一句话定位 + ASCII 架构图 + **「哪些东西不在仓库里」** | 素材/二进制不入库 |
| §1 环境 | 列出语言版本、必需外部工具（含**标准库移除类**依赖）、虚拟环境、依赖清单 | Python 3.9~3.14 / `audioop-lts` / ffmpeg |
| §2 代码获取 | clone 命令 + 镜像 + 浅克隆 + **克隆后目录实况** | 干净克隆 30 MB |
| §3 首次验证 | **自检工具 + 冒烟测试 + 全量测试**，逐条给出预期输出 | `doctor.py` / `ci_smoke.sh` / `pytest` |
| §4 数据准备 | 仓库无数据的场景必须给补齐路径 | `fetch_freepd.py` + `ingest_stems.py` |
| §5 启动 | 按模块分节，每节给参数表 + 实测输出 | 引擎 / 提示词 / 流服务 / 电台 / 专辑 |
| §6 FAQ | 每条 = **报错原文 + 根因 + 解法**，全部实测复现 | 12 条 |
| §7 工作流 | 分支 / 提交规范 / 提交前门禁 / 推送纪律 | 结构化前缀 + 三道门禁 |
| §8 约定 | 编号速查表，硬规则前置 | 10 条 |
| §9 模板 | 替换指引 | — |

**编写原则**（复用本文时务必保持）：

1. **数字必须实测** —— 不要照抄旧文档，用 `check_doc_counts.py` 之类的门禁兜底。
2. **命令必须给预期输出** —— 让新人能自己判断「对了还是错了」。
3. **故障写报错原文** —— 让新人能用报错文本搜到对应条目。
4. **区分「告警」与「失败」** —— 避免把预期状态说成故障（这是本仓 `doctor.py` 退出码 1 的教训）。
5. **认知落差优先讲** —— 新人卡住的地方通常不是「命令不会敲」，而是「不知道该期待什么」。

---

## 附：快速命令卡

```bash
# —— 环境 ——
python -m venv .venv && .venv\Scripts\activate          # Windows
pip install -r requirements.txt                          # 或 requirements.lock.txt

# —— 验证 ——
python remix/tools/doctor.py                             # 环境 + 素材自检
bash scripts/ci_smoke.sh                                 # 自检 + 冒烟
python -m pytest remix/tests music/tests -q              # 全量（343 条）

# —— 素材 ——
python remix/tools/fetch_freepd.py --out D:/tmp/src --limit 4
python remix/tools/ingest_stems.py --src D:/tmp/src --source-tag freepd
python remix/tools/detect_keys.py                        # 可选：调性标注

# —— 跑起来 ——
python remix/main.py --remix --seed 42                  # 混音引擎
python music/music_prompt_generator.py -c phonk          # 提示词
python music/prompt_driven_remix.py -c phonk             # 提示词 → 混音
python remix/tools/mixer_stream.py --port 8010           # 24 频道流
python radio/run.py                                      # 网络电台

# —— 贡献 ——
git checkout -b feature/xxx
bash scripts/ci_smoke.sh && python scripts/check_doc_counts.py
python scripts/check_encoding.py
git commit -m "feat(remix): xxx" && git push origin feature/xxx
```

---

*文档版本：2026-11-02 · 所有命令与数字均为当日实测 · 随仓库演进请同步更新本文*
