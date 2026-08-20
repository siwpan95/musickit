# 纯音乐风格提示词生成器 · Music Prompt Generator

一个从风格池（`styles/`）随机抽取要素、自动生成「纯音乐风格提示词」的小工具，用于 AI 音乐生成（Suno / Udio 等）的灵感与批量提示词生产。

---

## 目录结构

```
<项目根目录>/
├── music_prompt_generator.py   # 主程序（命令行）
├── music_prompt_gui.py         # 简易图形界面（tkinter）
├── validate_styles.py          # 风格池完整性自检
├── 优设标题黑.ttf             # GUI 项目字体（优设标题黑，中文简体，随项目分发）
├── styles/                     # 风格池（每个流派一个 JSON）
│   ├── synthwave.json
│   ├── lofi.json
│   ├── afrobeat.json
│   └── ...                     # 共 63 个风格
├── structure_moods.json         # 情绪/流派关键词 → 曲式模板规则（桥接器读取）
├── tests/                       # pytest 测试（test_bridge.py：桥接器映射与选音逻辑）
├── music_prompts_*.txt/json/csv # 运行 --export 后生成（默认名带时间戳，不覆盖旧导出）
├── 执行.bat / 运行GUI.bat       # 一键启动脚本
└── README.md
```

---

## 快速开始

```bash
# 列出所有风格（key → 名称 + BPM + 子流派数）
python music_prompt_generator.py --list

# 生成 1 条并直接打印
python music_prompt_generator.py

# 指定风格（如 phonk）
python music_prompt_generator.py -c phonk

# 跨类融合（随机混搭两类，乐器/情绪去重）
python music_prompt_generator.py --fusion

# 批量 20 条 + 种子（可复现）+ 导出 JSON
python music_prompt_generator.py -n 20 --seed 42 --export json

# 导出为可读 TXT（默认名带时间戳，如 music_prompts_20260815_2050.txt，不覆盖旧导出）
python music_prompt_generator.py -n 20 --export txt

# 自定义输出路径（可用绝对或相对路径；示例中的路径请替换为自己的目标位置）
python music_prompt_generator.py -n 10 --export txt -o <你的输出路径>/my_prompts.txt
```

---

## 命令行参数

| 参数 | 说明 |
|---|---|
| `-n, --num` | 生成条数（默认 1；导出模式下默认 10） |
| `-c, --category` | 指定风格 key（见 `--list` 输出） |
| `-e, --english` | 附带英文标签 `[Style]/[Mood]/[Tempo]...` |
| `--fusion` | 跨类融合生成（随机混搭两类风格） |
| `--list` | 列出所有分类及 key |
| `--export` | 导出格式：`json` / `csv` / `txt` |
| `-o, --output` | 导出文件路径（默认：脚本根目录下 `music_prompts_<时间戳>.<格式>`，不覆盖旧导出） |
| `--styles-dir` | 自定义风格池目录 |
| `--seed` | 随机种子，设置后结果可复现 |
| `--no-dedup` | 关闭批量生成去重（默认开启，保证每条差异） |

---

## 风格池字段规范

每个风格是一个 JSON 文件，约定字段如下：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `key` | string | ✅ | 唯一标识（英文小写，无空格），用于 `-c` 参数 |
| `label` | string | ✅ | 中文显示名（含原名） |
| `english` | string | 可选 | 英文原名 |
| `bpm` | string | ✅ | 速度区间，如 `"100-130 BPM"`（生成时会取整为具体数值） |
| `subgenres` | array | ✅ | 子流派列表，每项 `{ "name": "...", "bpm": "..." }`（`bpm` 可省略） |
| `instruments` | array | ✅ | 主奏乐器/音色 |
| `scales` | array | ✅ | 常用调式/音阶 |
| `moods` | array | ✅ | 情绪标签 |
| `elements` | array | ✅ | 风格化编曲元素 |
| `scenes` | array | ✅ | 适用场景 |

**示例**（最小可用）：

```json
{
  "key": "synthwave",
  "label": "合成波 Synthwave",
  "english": "Synthwave",
  "bpm": "80-118 BPM",
  "subgenres": [
    {"name": "Retrowave", "bpm": "100-118 BPM"},
    {"name": "Darksynth", "bpm": "90-115 BPM"}
  ],
  "instruments": ["合成器", "鼓机", "贝斯", "电吉他"],
  "scales": ["小调", "多利亚", "弗里几亚"],
  "moods": ["怀旧", "梦幻", "霓虹"],
  "elements": ["模拟合成器", "gated 混响", "霓虹质感"],
  "scenes": ["赛博都市", "夜间驾驶", "复古未来"]
}
```

---

## 风格池自检

每次扩充 `styles/` 后，运行自检确保格式正确：

```bash
python validate_styles.py            # 校验默认 styles/
python validate_styles.py -d 路径    # 指定目录
python validate_styles.py --strict   # 警告也视为失败（CI 用）
```

校验项：合法 JSON、必需字段齐全、列表字段非空、子流派含 `name`、key 唯一。

---

## 导出数据质量校验（demo_validator.py）

`demo_validator.py` 是一个**版本无关**的导出数据校验器，直接验证 `demo_test.csv` / `demo_test.json` 的数据质量，**不依赖任何硬编码的分类数量或提示词模板**，因此当风格池扩充到任意数量都不会误报。

```bash
python demo_validator.py
```

校验覆盖：

- CSV / JSON 条数一致、13 列结构完整
- 必填字段逐行非空（非融合时 `fusion_with` 允许为空）
- 中文无丢失（`style` / `prompt` 含汉字）
- BPM 格式 `\d+ BPM`（或自由速度文本）且数字型取值 40–260 合理
- 提示词均为纯音乐（兼容 `纯音乐` / `纯器乐` + `无人声` 多模板变体）
- 三种提示词模板均出现（多样性）
- 分类分布健康（无单一类别霸屏）
- `fusion` 字段一致（CSV 字符串 / JSON 布尔已归一化）
- 英文标签结构完整（`[Style]` + `no vocals`）
- CSV 与 JSON 逐条一致

数据文件查找顺序：生成器根目录（Downloads）→ 当前目录 → 脚本目录，从任意工作目录运行都能定位，不会因找不到文件而抛异常。

> 注：本仓库内的 `test_suite.py` 是**生成 `TEST_REPORT.md` 的测评脚本**（原 `新建文本文档.py` 已重命名为此 ASCII 名称，避免中文路径在命令行/脚本中引用异常）。其产物（`TEST_REPORT.md`、`demo_test.json`、`demo_test.csv`）统一写入项目根目录的绝对路径，无论从哪个工作目录运行都不会抛出到项目根目录之外。

---

## 生成算法说明

- **BPM 取整**：区间（如 `110-130`）随机抽取整数，让「速度」更真实。
- **融合去重**：`--fusion` 时混入第二类乐器/元素/情绪，用保序去重避免重复。
- **模板多样性**：3 套句式轮换，空字段自动省略，避免语病。
- **批量去重**：`-n` 批量时用指纹去重，保证每条差异（可用 `--no-dedup` 关闭）。
- **可复现**：`--seed` 固定随机种子，便于复现某次结果。

---

## 字体（GUI 中文显示）

项目内置 **优设标题黑**（`优设标题黑.ttf`，约 1.4MB）——标题黑体风格、中文简体，GUI 界面默认使用。此前版本内附的 `simhei.ttf` 系微软系统字体、随包分发违反许可，已移除；更早版本用的「周字宋体」为繁体字、不符合简体使用习惯，已替换为优设标题黑。

字体加载策略（`music_prompt_gui.py` 的 `load_project_font()`）：

1. **优先**：以进程私有模式加载项目根目录的 `优设标题黑.ttf`（Windows 下经 GDI `AddFontResourceExW` FR_PRIVATE 加载，仅本进程可见、退出即卸载，不污染系统字体表），界面默认使用优设标题黑；
2. **回退**：文件缺失或非 Windows 环境时，依次尝试系统已安装的 `SimHei` → `Microsoft YaHei` → tkinter 默认字体。

> 实现说明：`tkinter.font.Font` 不支持 `file` 参数，旧版"从文件注册字体"的写法从未真正生效（一直静默回退系统字体）；现行方案经实测可正确加载并返回真实字体族名 `优设标题黑`。

如需更换界面字体：把新字体文件放到项目根目录，并修改 `music_prompt_gui.py` 顶部的 `PROJ_FONT_PATH` 指向它即可。

---

## 提示词驱动混音（连接 musickit）

本工具生成的风格提示词，可直接作为 **G:\music\musickit\remix** 混音引擎的「混音驱动」：
提示词里的 `instruments / bpm / moods` 经 `G:\music\musickit\instrument_taxonomy.json` 规范分类体系
（242 乐器词 → 37 类目）映射成混音引擎的素材选择、速度与曲式模板；
真人 acapella 池（Coollider Acapellas）按 `vocal` 角色接入，自动在合适小节进入。
动物叫声独立为 **animal 池**，不再冒充人声；musickit 无样本的乐器（钢琴/弦乐/铜管/民族…）
会被跳过并记入 `gaps`，绝不假映射到错误池。

桥接器：`prompt_driven_remix.py`（与本文件同目录）

```bash
# 生成 1 条 phonk 提示词并直接驱动混音
python prompt_driven_remix.py -c phonk

# 批量 3 条不同风格，各驱动一段混音
python prompt_driven_remix.py -n 3 --out G:/music/musickit/music/prompt_mixes

# 先导出提示词 JSON，再喂给桥接器（两工具解耦协作）
python music_prompt_generator.py -n 5 --export json -o prompts.json
python prompt_driven_remix.py --prompt-json prompts.json

# 只看提示词→混音参数映射，不真正混音
python prompt_driven_remix.py -c trap --dry-run

# 发布安全模式：仅用 musickit 中授权层级为 free/pack 的素材
python prompt_driven_remix.py -c phonk --release-safe
```

**选音口径（2026-08-17 起，与混音引擎一致）**：

- 鼓/贝斯角色（含自动补的节奏骨架）**保底选取 ≥1 小节 loop/stem**；
- 旋律层（keys/strings/brass/woodwind/ethnic/guita/synth）**优先选 loop/BPM 显式素材**、
  其次排除单音采样（如 `EHn_susDyn_1-127_D3` 类文件），最后才全量回退——
  避免单音采样被当 loop 循环产生随机音高；
- 曲式模板选择规则外置在 `structure_moods.json`（同目录），改词表无需改代码。

> 本项目已整合进 `G:\\music\\musickit\\music`（单一仓库，消除跨项目路径风险）。\n> 运行桥接器需 `F:\Python314`（pydub + numpy + audioop-lts），与 musickit 混音引擎一致。
> 映射规则（乐器词→素材池、BPM 钳制、情绪→曲式模板）详见 `prompt_driven_remix.py` 顶部注释。

---

## 混音师风格着色（固定风格 × 随机风格整合）

G:\music\musickit\burbidge_album 的「固定风格」专辑管线（同一组 stems × 10 位混音师签名链）
已抽为共享模块 **burbidge_album/mixer_styles.py**。随机风格管线（本工具 + remix 引擎）
可把这 10 位混音师的「调音台签名」挂到任意一条随机混音上：

- 24 位混音师：burbidge / ghenea / clearmountain / marroquin / pensado / blake /
  lordalge / schmitt / mikedean / stent / wallace / maserati / joshua / ali /
  elmhirst / scheps / moulder / guzauski / albini / everett / elevado / shebib /
  power / zhoutianche（每位签名与逐总线参数见 burbidge_album/album/ALBUM_NOTES.md）；
- 分轨总线着色：鼓组（drum/cowbell）、贝斯（bass）、铺垫（synth/keys/strings/brass/
  woodwind/ethnic）、主奏与人声（guita/vocal）分别经过对应混音师的
  EQ/压缩/饱和/混响/宽度链；
- 母带：风格母带链（glue 压缩、M/S 宽度、饱和、目标 LUFS、砖墙限幅，峰值 -1.5 dBFS
  为 mp3 等有损编码留余量）。
- 频道形态工具：本地电台 remix/tools/mixer_radio.py、本地无限流 remix/tools/mixer_stream.py，
  与 Mubert 的异同及频道可行性见 MUBERT_COMPARISON.md。

    # 固定某位混音师（如 Mike Dean 的饱和太空感）
    python prompt_driven_remix.py -c phonk --mixer-style mikedean

    # 每条随机提示词各配一位随机混音师（--seed 可复现）
    python prompt_driven_remix.py -n 3 --fusion --mixer-style random --seed 42 --report out.json

    # 同一提示词 × 24 位混音师（A/B 对比，24 位依次替换）
    python prompt_driven_remix.py --prompt-json prompts.json --mixer-style burbidge

    # remix 引擎直连（不经过提示词桥接器）
    python remix/main.py --remix --mixer-style blake --seed 1

不传 --mixer-style 时行为与之前完全一致（原 phonk 处理链）。
随机混音所用混音师记录在 --report 的 mixer_style 字段。

## 测试

```bash
python -m pytest tests -q          # 桥接器单元测试（12 用例，不依赖真实素材库）
python validate_styles.py --strict # 风格池完整性
python demo_validator.py           # 导出数据质量校验
python test_suite.py               # 生成器全量测评（刷新 TEST_REPORT.md）
```
