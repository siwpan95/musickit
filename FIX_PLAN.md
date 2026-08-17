# G:\musickit 修复计划（v2）

> 依据：2026-08-13《musickit 项目评估报告》+ 用户裁定（含 16:43 补充）
> 原则：**先规划后执行**；所有素材移动只 move 不 delete；每阶段有 dry-run 与验收标准
> 对应关系：报告 §P0-1 → Phase 2；§P0-2/P1-2 → Phase 1；§3.2 功能问题 → Phase 3；§P2 → Phase 4

---

## 已执行变更记录

| 时间 | 变更 | 状态 |
|------|------|------|
| 2026-08-13 16:43 | `G:\musickit\.pass` → `G:\musickit\archived`（用户指示："垃圾桶"，类似 archived） | ✅ 已完成，40 个文件完好 |
| 2026-08-13 16:51 | **Phase 1 去重执行**：cowbell 174→114（移 60）、synth 50→23（移 27），共 87 个副本移入 `archived/dedupe_cowbell/`、`archived/dedupe_synth/`，0 失败；archived 自身 40 文件未动（用户指示）；remix CLI 冒烟通过（seed 42）；移动记录 `remix/tools/dedupe_manifest.json` | ✅ 已完成 |
| 2026-08-13 17:22 | **Phase 2 执行**：下载 4 个 MusicRadar SampleRadar 免费包（EBM/Deep House/Funk Keys/90s Hip-Hop，共 567MB，royalty-free）；审计 1249 音频→620 候选；归一化入库 **199 个真实采样**（synth (51)~ 起，44.1k 立体声 16bit、峰值-3dBFS、去重）；23 个机生成占位全部移入 `archived/synth_placeholder/`；synth 目录现 100% 真实采样；频谱集中度 0.13~0.46 vs 旧占位 0.35~0.80；remix 冒烟通过（seed 99）；脚本：`remix/tools/audit_pack.py` + `ingest_synth.py`；需邮箱结账源指南：`archived/downloads/MANUAL_DOWNLOAD_GUIDE.md` | ✅ 已完成 |
| 2026-08-13 17:53 | **Phase 2 扩展·剩余素材分类入库**：downloads 中 synth 之外的音频（bass/beat/鼓点等）按类别全量入库——`ingest_categories.py`（drum 100ms~16s、bass 0.3~12s、synth 0.3~8s；路由：drum 关键词→drum/，bass/808→bass/，其余→synth/；sha256 去重+跳过已入库 199）→ **drum +467、bass +164、synth +301，共 932 个**。目录现况：bass 422 / drum 725 / synth 500 / guita 259 / cowbell 114。三个目录 manifest 齐全；remix 冒烟通过（seed 7，选到新入库 drum (399)/bass (233) 等） | ✅ 已完成 |
| 2026-08-13 18:17 | **Phase 3 功能修复（按严重度）**：F1 loop 化 beat（新增 `core/loop_slicer.py`：BPM 网格、能量峰定位切片、ffmpeg 只解码切片；整曲→1~2 小节 loop，短音→循环/点缀；实测输出 27.4s@140BPM 4.8MB，旧版为 3~14.6 分钟 30~154MB）；F2 时长可控（`--bars` 默认 16、`--bpm` 默认随机 110~150，实测 8 小节→16.3s）；F3 v1 完成（只切不拉伸，v2 atempo 留待）；F4 内存（8kHz 包络扫描+切片式载入，整曲不再进内存，跑一次 12.8s）；F5 路径解耦（`MUSICKIT_ROOT` 环境变量）；F6 内容去重（时长+前 0.5s 哈希指纹，选音时剔除重复采样）；F7 文档（MIGRATED.txt/README 更新）。测试 77→**86 passed**；冒烟 seed 42/1 通过 | ✅ 已完成 |
| 2026-08-13 18:35 | **F3-v2 + 输出加长 + Phase 4**：F3-v2 变速对齐（`estimate_bpm` 自相关估速 + `load_slice` atempo 拉伸 + `parse_bpm_hint` 从 manifest 路径提示取源 BPM，比率钳制 0.85~1.18）；默认输出 16→**32 小节（≈55s@140BPM）**，>12 小节自动段落编排（intro 鼓+旋律 → +bass → drop +牛铃/synth → outro 2 小节淡出），回答"20 多秒太短"；Phase 4 总索引（`tools/build_manifest_index.py` → `G:\musickit\manifest_index.json`：5 目录 manifest 合并 + **775 个 stem 全部反查到歌名**）+ archived 定位固化（根 `README.md` + `archived/README.md` 政策：只进不出/不参与混音/移动可回溯）。测试 **88 passed / 2 skipped**；实测 32 小节 54.9s wav 混音通过 | ✅ 已完成 |
| 2026-08-13 18:42 | **A/B 段落变化（防单调）+ 索引定时刷新**：`best_loop_start`/`prepare_material` 支持搜索区间（A=曲首 0~120s，B=中段 60~240s，同曲不同段落各切一片；短素材 B=同类另一文件）；`build_arrangement` 支持 `seg_b` + `variant_every_bars`（旋律层 guita/synth 每 4 小节 A/B 交替，drum/bass 每 8 小节，块内循环对齐小节网格）；>12 小节才启用。同 seed 前后输出哈希不同 → 变体生效。测试 **91 passed / 1 skipped**。自动化：`automation-1786617582786`「musickit 总索引定时刷新」每日 02:30 重跑 build_manifest_index.py | ✅ 已完成 |

**`archived`（原 .pass）定位**：项目的**垃圾桶/归档区**——所有冗余副本、机生成占位音频、过期素材一律移入此处，只进不出（可手动找回），不参与混音。remix 代码不引用它，改名无副作用（已 grep 确认无代码引用）。

---

## 用户裁定汇总（已吸收）

1. `guita` 是有意把 other 轨当吉他音轨用 → 报告已改「项目约定」，不修复
2. 混音项目已独立出 bloodmusic → 报告已改「独立主线」，不再谈双副本收敛
3. 重复签名副本转移至 `archived` 文件夹 → Phase 1
4. 功能问题/改进建议先规划修复计划 → 本文档（Phase 3 / Phase 4）
5. synth 用真实采样替换，路线为**下载免费采样包** → Phase 2
6. （16:43 补充）synth 机生成音频引入真实采样后**全部**移入 archived；`.pass` 改名 `archived` → 已完成

---

## Phase 1 · 重复文件转移至 `archived`（数据卫生，低风险）

### 1.1 去重范围与规则

| 目录 | 现状 | 保留 | 移入 `archived` |
|------|-----:|-----:|----------------:|
| `cowbell` | 174 | 114 | 60 → `archived/dedupe_cowbell/` |
| `synth` | 50 | 23 | 27 → `archived/dedupe_synth/` |
| `archived` 自身 | 40 | 14 | 26 → `archived/_redundant/` |

**规则**：
- 判定：内容签名相同（文件大小 + 首尾 64KB SHA-256，与评估报告同口径）
- 保留：每个签名组中编号最小的文件（如 `cowbell (1).mp3` 组内保留，`(109)/(115)/(7)` 移走）
- 移动目标：`archived/dedupe_cowbell/`、`archived/dedupe_synth/`、`archived/_redundant/`——子目录隔离，避免同名冲突，且标明来源
- **绝不删除**：archived 是垃圾桶，任何误操作可从归档找回

### 1.2 执行步骤

1. 写 `tools/dedupe_to_archive.py`（放在 `G:\musickit\remix\tools\`，随项目走）：
   - `--dry-run` 默认开启：只打印计划移动清单 + 统计，不动文件
   - `--apply`：按计划执行 `shutil.move`，每步写 `dedupe_manifest.json`（`原路径 → 新路径 → 签名`）
   - 对 archived 自身的去重单独 `--target archived` 模式
2. dry-run 输出给用户过目 → 确认后 `--apply`
3. 验收：复跑评估用的哈希分析（`musickit_analysis/analyze_audio.py`），确认：
   - `cowbell` 174→114、`synth` 50→23、`archived` 40→14（+归档文件齐全）
   - `remix/main.py --remix` 冒烟测试仍能选音混音（去重后目录结构不变、后缀不变，理论无影响，实测确认）

### 1.3 风险

- 极低：仅 move，manifest 可回溯；唯一注意 Windows 下同名 mp3/wav 不互相覆盖（子目录已隔离）。

---

## Phase 2 · synth 用免费采样包替换（用户指定路线）

### 2.1 候选采样包（执行时逐个人工确认授权条款）

| 候选源 | 类型 | 授权 | 备注 |
|--------|------|------|------|
| **MusicRadar SampleRadar** | synth loop/lead/keys | Royalty-free（勿转售包本体） | ✅ 已入库 199 个（EBM/Deep House/Funk Keys/90s Hip-Hop） |
| **Signature Sounds**（用户指定新增） | 实录音/合唱/钟声/氛围 | **CC0**（可商用免署名） | 需三步结账：Your Email→Payment→Review（£0.00），见手动下载指南 |
| **Cymatics Free Download Vault** | 鼓组/旋律 loop/one-shot | Royalty-free（官网条款） | 需邮箱收取下载链接 |
| **99Sounds（Gumroad）** | 硬件合成器实采样 | Royalty-free | Bass City/Simply Space/MGF Audio，$0 结账需邮箱 |
| **Splice Sounds 免费区** | one-shot/loop | 需注册账号 | 可精挑 synth lead/pluck |
| **freesound.org** | one-shot | **CC0 最稳**（CC-BY 需署名） | 需注册账号下载 |
| **Ghosthack 免费包** | 采样/loop | Royalty-free | 定期放免费包 |

目标音色（贴合 phonk）：暗色 synth lead、pad 垫底、pluck 拨弦、氛围键琴，one-shot 或 1~2 小节 loop，时长 0.3~8s。

### 2.2 入库流程

1. **下载**：包下载到 `G:\musickit\archived\downloads\`（暂存，不入 synth）
2. **审计**（脚本 `tools/audit_pack.py`）：ffprobe 全量扫描 → 过滤（格式可解码 / 时长 0.3~8s / 非静音 / 采样率≥44.1k）→ 输出候选清单
3. **归一化入库**（脚本 `tools/ingest_synth.py`）：
   - 统一转 44.1kHz / 立体声 / 16bit wav（用 remix 内置 ffmpeg）
   - 首尾静音修剪、峰值归一化 -3 dB
   - 命名沿用 `synth (N).wav` 编号体系（`main.py` 兼容，**代码零改动**），从 51 起续号
   - 每个文件记录：`编号 → 来源包 → 原始文件名 → 授权 → 时长`，写入 `synth/manifest.json`
4. **替换占位（全部移入垃圾桶）**：synth 现有 50 个文件**全部**是机生成占位，全部移入 archived——
   - Phase 1 已把 27 份重复副本移入 `archived/dedupe_synth/`
   - 本步骤把剩余 23 个唯一占位音移入 `archived/synth_placeholder/`（不删，遵循"只移不删"）
   - 至此 synth 目录被真实采样完全接管，编号从 51 起
5. **验收**：
   - synth 目录 100% 为真实采样（复跑音调分析：过零率应 >0.2、top3 能量占比应 <30%，与占位特征明显区分）
   - `main.py --remix --count 5 --seed 42` 冒烟通过
   - manifest.json 完整、每个文件可溯源授权

### 2.3 风险

- **授权合规是唯一硬风险**：入库前必须逐包确认 license 并写入 manifest；CC0/royalty-free 可商用自用，CC-BY 需保留署名（manifest 里记原作者）。不明来源的一律不入库。
- 包体可能偏大（下载+解包占临时磁盘，`archived/downloads/` 用后清空）。

---

## Phase 3 · 功能问题修复（按严重度排序）

### F1【高】整曲 mashup → loop 化 beat

- **现状**：`run_remix` 把 1~14.6 分钟整曲直接叠加，产出 3~14.6 分钟、30~154MB 的噪声叠加物
- **方案**：
  1. 新增 `core/loop_slicer.py`：按 BPM 网格（默认 100~160 随机或 manifest 指定）把整曲切成 1/2/4 小节 loop（140 BPM 时 1 小节≈1.71s）；切片起点对齐能量峰（避免从静音/半拍切）
  2. `run_remix` 改为：每轨随机取 1~2 个 loop + 编排骨架（鼓 loop 铺底 → bass 低音线 → guita 旋律片段 → cowbell/synth 点缀层按小节网格落位），输出 8~16 小节（约 15~30s@140BPM）
- **改动点**：`main.py`（`run_remix`/`_pick_random_tracks` 选片逻辑）、新增 `core/loop_slicer.py`
- **验收**：默认输出 ≤30s、≤10MB；`--bars N` 可调长度；人工听感抽查不再是"多首歌同时放"

### F2【高】输出时长可控

- **方案**：CLI 增加 `--bars N`（默认 16）；GUI 混音保持整轨语义（手动模式不受影响）
- **验收**：`--bars 8` 输出严格 8 小节

### F3【中】BPM 对齐 / time-stretch

- **方案**：第一阶段（v1）只做"按统一 BPM 网格切分"，**不做 time-stretch**（保持原速切片，phonk 常用原速采样，风险最低）；第二阶段（v2）再加 ffmpeg `atempo` 变速对齐
- **验收 v1**：切片边界与 BPM 网格一致，loop 首尾无爆音

### F4【中】内存优化

- **现状**：单轨 30~58MB 整轨载入，5 轨峰值 200MB+
- **方案**：loop 化后素材天然变小（<2MB/片）；另在 `audio_loader` 支持"只读前 N 秒"切片式载入，避免整轨进内存
- **验收**：`--remix` 峰值内存 <100MB（对比当前约 200MB+）

### F5【中】素材路径解耦

- **现状**：`_MUSICKIT_ROOT` 硬编码为 remix 上级目录
- **方案**：`MUSICKIT_ROOT` 环境变量优先 + 相对路径回退 + 缺失时明确报错
- **验收**：把 remix 目录复制到别处、设 `MUSICKIT_ROOT` 后仍可跑通

### F6【低】同采样双格式去重

- **现状**：cowbell 同一采样同时存在 mp3 与 wav，随机选音可能两种格式同时入选
- **方案**：选音时按"内容签名"去重（复用 Phase 1 的签名函数），同签名只允许一种格式入选
- **验收**：多次 `--remix` 选音日志中不再出现同一采样双格式同场

### F7【低】文档更新

- `MIGRATED.txt` → 「musickit 独立项目，历史：迁移自 bloodmusic/remix」
- README 补：`guita` = other 轨有意用作吉他轨（项目约定）、`archived` = 垃圾桶/归档区定位（原 .pass）、synth manifest 说明
- **验收**：文档与现状一致（无"迁移至 bloodmusic 内部"等过时表述）

---

## Phase 4 · 数据治理（收尾）

1. **manifest.json 总索引**：bass/drum/guita 记录 `编号 → 歌名 → stem 类型`（从 `radio_music_stems` 目录名反查补齐）；cowbell/synth 记录来源与授权
2. **磁盘优化（可选）**：27.3GB 整曲 stem 保留（loop 化后仍按需回切）；若磁盘紧张，可把不常用整曲移到冷存储
3. **`archived` 定位固化**：README 写明 `archived` = 垃圾桶/归档区（冗余副本 + 占位音频 + 过期素材），仅存档不参与混音

---

## 执行顺序与依赖

```
Phase 1 去重（独立，可立即做，~1 小时含确认）
   │
Phase 2 synth 采样包替换（依赖：需先定包清单，下载量 1~5GB）
   │
Phase 3 F1+F2（核心功能，依赖 Phase 1/2 完成后的干净素材库）
   ├─ F3 v2（依赖 F1）
   ├─ F4（F1 后自然达成，补 audio_loader 小改）
   ├─ F5/F6/F7（独立小项，可并行）
   │
Phase 4 治理收尾（依赖以上全部）
```

- **Phase 1 与 Phase 2 可并行**：去重脚本与采样包下载互不冲突（Phase 1 只动 cowbell/synth/archived 的冗余副本，Phase 2 写 synth 新文件）
- **暂停点**：每个 Phase 结束产出验收清单，确认后再进下一 Phase

## 总体风险提示

- 采样包授权：入库前人工确认 license，写入 manifest 可溯源（CC0 优先）
- 全部移动操作可回溯：`archived` 垃圾桶 + manifest，无任何删除动作
- Phase 3 改动 `main.py` 选音/混音逻辑，改前先跑通现有 77 个测试作为基线
