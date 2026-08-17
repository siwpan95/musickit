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
```

素材根目录可用环境变量 `MUSICKIT_ROOT` 覆盖（默认 remix 的上级目录）。

**目录约定**：
- `guita/` = Demucs 分离的 other 轨，**有意作为吉他/旋律轨使用**（项目约定）
- `archived/` = 垃圾桶/归档区（冗余副本、占位音频、下载暂存），不参与混音
- 各素材目录下的 `manifest.json` 记录编号 → 来源 → 授权，可溯源

**phonk 风格参考（联网调研）**：典型 phonk beat 由多层构成 ——
鼓组（1~2 轨）、808 贝斯（1 轨）、牛铃 / 旋律采样（1 轨）、人声切片（可选）、
其它 synth / 采样。最小可用骨架为 3 轨（鼓 + 贝斯 + 旋律），
典型完整制作约 4~6 轨。本工具默认随机选 3 条，可用 `--count` 调整。

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

## 项目结构

```
remix/
├── main.py                 # 程序入口 + 依赖检查 + 随机混音 CLI
├── core/
│   ├── audio_loader.py     # 加载 / 参数统一 / 导出
│   └── audio_mixer.py      # 混音引擎（纯业务逻辑，零 GUI 依赖）
├── gui/
│   └── main_window.py      # tkinter 主界面（仅音频混音）
├── utils/
│   └── progress_reporter.py# 线程安全进度报告
└── tests/                  # pytest 测试套件
```

## 测试

```bash
pip install pytest
pytest tests/ -v
```

> 注：涉及 GUI 的进度报告测试在缺少 tkinter / Tcl 环境时会自动跳过（skip），
> 不会失败。

---

## 提示词驱动混音（来自 G:\tools\music）

本引擎可被 **G:\tools\music\prompt_driven_remix.py** 以「提示词」驱动：
`music_prompt_generator` 生成的结构化提示词（乐器 / BPM / 情绪）经该桥接器映射为本引擎的
`run_remix(tracks, bpm, structure)`，从而用真实素材产出混音。

- 提示词里的 `instruments` → 经 `G:\musickit\instrument_taxonomy.json` 规范分类体系映射
  （music 工具 242 个乐器词 → 37 个规范类目 → musickit 池），**避免把不同乐器家族压进粗池**。
  - 真人 **acapella 池**（`G:\musickit\acapella`，Coollider Acapellas）按 `vocal` 角色接入；
  - 动物叫声已独立为 **animal 池**（`G:\musickit\animal`），不再冒充人声；
  - 钢琴/弦乐/铜管/笛箫/民族乐器等 musickit 无样本的类目会被跳过并记入 `gaps`，绝不假映射。
- `bpm` → 混音目标速度
- `moods` / `subgenre` → 曲式模板（`classic_drop` / `ambient_ghost` / `loop_stack`）

运行桥接器需 `F:\Python314`（pydub + numpy + audioop-lts），并把 `MUSICKIT_ROOT`
指向 `G:\musickit`（桥接器已默认设置）。详见 `G:\tools\music\prompt_driven_remix.py`。
