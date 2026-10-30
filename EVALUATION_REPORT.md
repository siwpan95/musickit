# G:\music\musickit 项目评估报告

> 评估日期：2026-08-13
> 评估方式：本地实测（ffprobe 参数探测 / SHA-256 哈希判重 / Goertzel 频谱分析 / 源码审查 / pytest 实跑）
> 项目规模：28 GB（其中素材库 27.3 GB，应用代码 685 MB）

---

## 一、项目定位与血缘

`G:\music\musickit` 是一个 **phonk 风格随机混音项目**，由两部分组成：

| 部分 | 内容 | 来源 |
|------|------|------|
| 素材库 | `bass` / `drum` / `guita` / `cowbell` / `synth` / `archived`（原 `.pass`） | 多来源（见下） |
| 混音应用 | `remix/`（main.py + core/gui/utils/tests + 内置 ffmpeg） | 历史上迁移自 `G:\tools\bloodmusic\remix`，**现已独立** |

`remix/MIGRATED.txt` 记录该应用历史迁移关系；**经确认（2026-08-13），musickit 现已独立于 bloodmusic**，为独立主线。bloodmusic 本体（4.8 万行的程序化游戏音频合成引擎）仅作历史参考。

---

## 二、素材库逐目录实测评估（核心）

### 总览

| 目录 | 文件数 | 体积 | 唯一内容 | 性质判定 |
|------|-------:|------|--------:|----------|
| `bass` | 258 | 9.1 GB | ~258 | ✅ 真实音乐（Demucs 分离 bass 轨） |
| `drum` | 258 | 9.1 GB | ~258 | ✅ 真实音乐（Demucs 分离 drums 轨） |
| `guita` | 259 | 9.1 GB | ~259 | ✅ 真实音乐（other 轨**有意**用作吉他轨，项目约定） |
| `cowbell` | 174 | 60 MB | **114** | ✅ 真实 one-shot 采样，但有 60 份重复拷贝 |
| `synth` | 50 | 15 MB | **23** | ❌ **机生成占位音频**（用户所指问题） |
| `archived`（原 `.pass`） | 40 | 5.7 MB | **14** | 🗑️ 垃圾桶/归档区：占位/冗余（2026-08-13 已按用户指示改名） |

### 2.1 bass / drum / guita —— 真实，但"粒度"用错了

**实锤证据**：抽 30 个文件与 `G:\music\radio_music_stems` 做哈希比对，**100% 命中**——

- `bass (10).wav` = `Chinese Football - 电动少女\bass.wav`
- `drum (100).wav` = `Billie Eilish - bury a friend\drums.wav`
- `guita (1).wav` = `Côme - La gloire à mes genoux\other.wav` ← **other 轨，不是吉他**

三个目录的时长分布完全一致（min 55.4s / 中位 199.7s / max 875.5s），佐证三者来自同一批歌曲的 stem。

**问题**：
1. **全是整曲**（0.9~14.6 分钟），不是 phonk 制作所需的采样/loop。phonk 的最小单元是一小节（约 2~4s）循环切片。
2. **`guita` = other 轨有意用作吉他轨（项目约定，非缺陷）**：Demucs htdemucs 只产出 vocals/drums/bass/other 四轨，"other" 除吉他外还含钢琴/弦乐/垫底等剩余乐器。**已与用户确认：是有意把 other 轨当吉他/旋律轨使用**，故此项不作为问题，仅如实记录（后续混音时可留意 other 轨中非吉他成分的占比）。
3. 27.3 GB 是全量 stem 拷贝（radio_music_stems 已有 327 首分离完成，此处取用 258 首）。

### 2.2 cowbell —— 真实 one-shot，含大量内部冗余

- 174 个文件中 **114 个唯一采样**（110 个 mp3 + 4 个 wav），时长 0.08~1.4s，符合 phonk 牛铃 one-shot 特征，**质量可用**。
- 但存在 58 组重复签名，典型模式：`cowbell (100)~(109)` 复制自 `(42)~(50)`，`(110)~(121)` 复制自 `(2)~(13)`……即约 60 份是**同一采样的重命名拷贝**（浏览器重复下载自动加 (N) 所致）。

### 2.3 synth —— ❌ 机生成占位音频（本报告重点）

**量化实锤**：

| 证据 | 数据 |
|------|------|
| 有效内容 | 50 个文件只有 **23 个唯一内容**；其中 3 个原型各被复制 10 份（211,724 B / 61,780 B / 705,644 B 三组） |
| 时长 | 0.35 ~ 4.0 s（44.1kHz 立体声 16bit） |
| 频谱集中度 | `synth (13)` 等文件 **80.1% 能量集中在 3 根谱线**（169.5 / 339 / 508 Hz）；真实乐器采样谐波+噪声丰富，单频占比通常 <10% |
| 过零率 | 0.002 ~ 0.15（真实乐器/鼓采样普遍 0.25+；0.002 意味着近乎纯净正弦） |
| 波形特征 | `synth (1)/(11)/(16)` 为 ~50Hz 低频嗡嗡声；`(2)/(12)/(17)` 为 ~3.6kHz 高频纯音簇——典型振荡器合成音（正弦/简单波形叠加） |

另有 `archived`（原 `.pass`）目录：40 个文件仅 14 个唯一内容（两种字节尺寸循环），全部文件峰值 **0.7789 完全一致**，同为同批机生成占位；**当前 remix 代码不引用它**。2026-08-13 已按用户指示改名为 `archived`，定位为项目**垃圾桶/归档区**（冗余副本、占位音频、过期素材的最终归宿）。

**影响**：`remix/main.py` 把 `synth` 列为 phonk 五类素材之一（`_SOURCE_CATEGORIES`），`--count ≥ 4` 时 synth 会作为"phonk 标志层"被随机选入混音 → **每条含 synth 的产出都被占位音污染**，且 50 选 1 的随机里约 60% 概率命中同一批重复原型。

---

## 三、remix 应用评估

### 3.1 代码健康度 ✅

`/Python314/python.exe -m pytest tests/` 实测 **77 passed / 1 skipped**。README 对 Python 3.13+ 需 `audioop-lts` 的说明准确，`requirements.txt` 已含该补丁。内置 `bin/ffmpeg.exe` 实现零外部依赖。

### 3.2 功能问题（按严重度）

1. **"随机混音"实为整曲 mashup**：`run_remix` 把 3~5 条 1~14 分钟整曲直接 RMS 归一化后叠加，无 BPM 对齐、无节拍网格、无 loop 切片。已产出 9 个文件（30~154 MB，时长 3~14.6 分钟）——这是**噪声叠加**，不是 phonk beat。
2. **内存开销**：pydub 整轨载入内存，单轨 30~58 MB，5 轨峰值约 200+ MB。
3. **素材与代码硬耦合**：`_MUSICKIT_ROOT` 硬编码为 remix 的上级目录，目录改名/迁移即失效。
4. **cowbell 双格式混存**：mp3 与 wav 内容重复，随机选音可能选中同一采样的两种格式。
5. ~~双副本维护风险~~（已澄清）：**musickit/remix 已独立于 bloodmusic**，是独立主线。`MIGRATED.txt` 内容已过时，建议更新为「musickit 独立项目，历史：迁移自 bloodmusic/remix」。

---

## 四、总体结论

| 维度 | 评价 |
|------|------|
| 素材真实性 | bass/drum/guita/cowbell 为真实音频；**synth/archived（原 .pass）为机生成占位**（与本报告主题一致） |
| 管线可用性 | 代码可跑通、可出 wav/mp3，测试全绿 |
| 产品完成度 | 低——"phonk 混音"名不副实：占位 synth + 整曲 mashup 无 beat 逻辑 |
| 数据卫生 | 差——synth 54% / archived（原 .pass）65% / cowbell 34% 是重复内容；27.3 GB 整曲拷贝支撑的却是随机 mashup |

**一句话**：骨架（真实 stem + 可用混音代码）已具备，但 **synth 占位音未替换 + 无 loop/beat 层** 这两件事锁死了产出质量上限。

---

## 五、改进建议（按优先级）

### P0-1 用真实采样替换 synth（本期主题 · 用户裁定：下载免费采样包）

1. **主路线（用户指定）：下载免费采样包**——Cymatics 免费包 / Splice 免费下载 / freesound.org（CC0 最稳）等，下载前逐包核查授权条款；候选清单与入库流程见《修复计划》Phase 2。
2. **备选补充：从 `G:\music\radio_music_stems` 的 other 轨切 loop**——零新增版权、贴合 phonk 采样美学，作为免费包数量不足时的补充。
3. **不推荐**：继续用振荡器合成音色冒充"采样"（用户已明确要真实采样）；bloodmusic 自带的 18 站音效爬虫在自家评估报告中被标注为合规隐患，勿直接沿用。

### P0-2 `archived`（原 `.pass`）= 项目垃圾桶/归档区（用户裁定，已改名）

2026-08-13 已按用户指示把 `.pass` 改名为 `archived`。今后 `archived` 是**垃圾桶**：冗余副本、机生成占位音频、过期素材一律移入此处——去重时冗余副本**移动**（不删除）至 `archived/` 下按来源命名的子目录（见《修复计划》Phase 1）；Phase 2 替换 synth 时，**全部 50 个机生成占位音**一并移入 `archived/`（27 份副本归 `dedupe_synth/`，23 个唯一占位归 `synth_placeholder/`），保证全程可回溯、只进不出。

### P1-1 ~~`guita` 正名~~（撤回）

用户已澄清：`guita` 是**有意**把 other 轨当吉他/旋律轨用，属项目约定，保持现名。仅保留后半条建议：建 manifest.json 记录 `编号 → 歌名 → stem 类型`，找回匿名编号丢失的歌名映射。

### P1-2 素材去重（转移至 `archived`，用户裁定）

- cowbell 174 → 114、synth 50 → 23、archived 40 → 14：每个重复签名组保留编号最小的文件，其余冗余副本**移动**（非删除）至 `archived/dedupe_<来源目录>/` 归档；
- 全程 dry-run 先行 + move manifest 记录，可回溯；
- 建立 `manifest.json` 索引，替代"浏览器下载名 (N)"式管理。

### P2-1 phonk 管线升级（从 mashup 到 beat）

- 切片 loop 化：所有素材切到 1/2/4 小节循环；
- BPM 对齐：time-stretch 到统一速度（可参考 bloodmusic `effects/` 的实现思路；项目已独立，代码需自行移植维护）；
- 编排逻辑：鼓+bass+旋律+牛铃+synth 的段落化编排，替换现在的纯随机叠加（可借鉴 bloodmusic `music/` 的欧几里得节奏/编曲思路）。

### P2-2 ~~双副本收敛~~（已澄清：musickit 独立）

musickit/remix 已独立于 bloodmusic，无需收敛。仅需更新 `MIGRATED.txt` 为「musickit 独立项目，历史：迁移自 bloodmusic/remix」，README 同步说明。

### P2-3 磁盘优化

27.3 GB 整曲 stem 若只为 phonk 服务，切出 loop 后原曲可只留索引（按需回切），素材库可压缩到数百 MB 级。

---

*附：本次分析产物——`musickit_analysis/analyze_audio.py`（可复跑的批量分析脚本）与 `musickit_analysis/analysis_result.json`（全量统计原始数据）。*
