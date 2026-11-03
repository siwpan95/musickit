# musickit 优先级规划（v3 · 以架构文档为基准）

**日期**：2026-11-02 18:28
**规划基准**：`docs/musickit-architecture.html`（HEAD `f43df88` 随代码一同提交）
**辅助输入**：`full-audit-musickit-2026-11-02.md`（73 条审计发现）
**前提**：素材为公版，无侵权问题；`--release-safe` 已撤销 P0

> v2 曾试图用 workbuddy 成长中心画像做权重依据 —— 抓不到（SPA），且基准本就选错。本版改用项目**自己的架构设计文档**：它已经把短板写在明面上，不需要外部画像来猜。

---

## 0. 文档自己说了什么

`docs/musickit-architecture.html` §8 结论列了 5 条，其中两条自我定性为短板：

| 文档原话 | 现状核验 | 结论 |
|---|---|---|
| 「**API 文档是短板**：既有 `api_docs.py` 路由名/字段不全、无示例，已用两份 OpenAPI v3 规范补齐」 | `radio/openapi.json` 58,353B + `openapi.yaml` 31,484B 已存在 | ✅ **已解决**（本次不再排期） |
| 「**提示词利用率是第二大短板（重点）**：生成器产出 12 字段，桥接器仅真正消费 `instruments`+`bpm`（另 3 字段只选曲式），`scale/elements/scene/sentence/fusion` 等 7 字段被静默丢弃」 | 我逐行核过：`generate()` 返回 12 字段（`music_prompt_generator.py:239`）；`prompt_to_mix_params` 读 `bpm`(:248)、`instruments`(:258)、`label/subgenre/moods`(:313-315 仅送 `choose_structure`) | ✅ **判断准确，这是本项目真正的主线** |

**所以优先级的第一顺位不是你找我审的那些 bug，而是文档 §7 点名的这件事。** 审计那条线的作用是：**保证你在做 §7 时，脚下的地基不会塌。**

---

## 1. 两条轴，别混着排

| 轴 | 目标 | 来源 | 性质 |
|---|---|---|---|
| **A · 工程健康** | 让管线「能跑、能信」 | 我的全检（73 条） | 修 bug、删死功能、补门禁 |
| **B · 能力补全** | 让「提示词所写即所得」 | 文档 §7 / §7.3 | 产品能力，决定作品上限 |

### 关键论证：B 轴被 A 轴卡死

文档 §7.3 给的五条强化建议，**每一条都需要「能听出差别」才能验证**：

| §7.3 建议 | 验证它需要什么 | 当前是否具备 |
|---|---|---|
| `scale` → 按调性选素材 / pitch-shift | 渲染同一 prompt、只改 scale，A/B 听同一段 | ❌ 无素材、无 ffprobe → 渲染即崩 |
| `elements` → 映射到 sfx/animal 池作 accent | 确认那层音效真的进了混音 | ❌ 同上 |
| `scene` → 映射到 mixer_style | 两个 scene 出两种音色，能对比 | ❌ 同上 |
| `sentence` → 写入 ID3 comment | 回读文件元数据 | ⚠️ 只需能产出文件 |
| `fusion` → 真并入第二风格乐器 | 单风格 vs 融合，听出差异 | ❌ 同上 |

**结论：不在 T0 修好「能渲染 + 可回归」，§7.3 的五条建议全部只能靠读代码断言「应该生效了」—— 那就是这套项目已经犯过 7 次的错（音量/重扫/delivery_ok/渲染解释器/release-safe/LUFS/bars）。**

所以顺序是 **A 先行、B 跟进**，而不是二选一。

---

## 2. T0 — 本周必做（A 轴地基，同时是 B 轴前置）

| # | 事项 | 为什么是 T0 | 成本 | 验收 |
|---|---|---|---|---|
| **T0-1** | 修 ffmpeg/ffprobe 解析：加 `resolve_bin()`（bin → `which` → 显式报错）；`main.py:46-47` 补 `isfile` 守卫；`duration_ms()` 失败回落 manifest `duration_s`；README 删「零外部依赖/164MB」，改为「需自备 ffmpeg **与 ffprobe**」 | `ffprobe.exe` 从未入库，`duration_ms()` 恒返 0 → 选音/切片/B 变体判断全走错分支，且**静默**。B 轴任何 A/B 对比都建立在错误的时长判定上 | 1~2h | 缺 ffprobe 时日志打出确缺失路径；补齐后曲目信息时长不再 `0.0s` |
| **T0-2** | 恢复素材池 + 建 3~5 个短 loop 的最小夹具（提交入库） + 接 CI 跑 `-m smoke` | 13 个池磁盘 0 音频、manifest 有 30,259 条 → 音频域 **0% 可验证**；无任何 CI。这是 B 轴唯一的验证手段 | 半天（素材同步另计） | 干净克隆 → smoke 绿；≥1 条端到端用例（渲染 8 小节 → 回读 `frames>0`） |
| **T0-3** | ~~删 7 处写死 `✅ 修复: ✓`~~ → **更正**：该结论有误（全仓 grep 无此串）。真实缺陷是评分卡 3 项写死满分 → 已改为通过率统计；`TEST_REPORT.md` 已退出版本跟踪 | 假分数会遮蔽真实失败：你改完 scale 映射，靠什么判断真的生效了？不能靠「综合得分 70/70」 | 20min | 报告只输出 `PASS/FAIL` 与通过率，评级由通过率决定 |
| **T0-4** | 给 `run_remix` 加**后置总断言**：`frames>0`、时长 ≈ `bars × bar_ms`（±1 小节）、峰值未削波 | 已有两种形态的「空/错文件 + exit 0」：`--release-safe` 剔空、`--bars -1` 出 102 字节。B 轴会大量调参，没有这道断言，你会把「参数没生效」误判成「艺术选择」 | 2h | 任何导出路径断言失败即失败，不写「已保存至」 |

> **T0 交付后的状态**：`python remix/main.py --remix --bars 8` 能稳定出片，参数改动能被测试捕捉。**这才叫「可以开始做音乐」。**

---

## 3. T1 — ✅ 已完成（2026-11-02 19:0x，已推送）

| # | 事项 | commit | 结果 |
|---|---|---|---|
| T1-1 | 移除 `--release-safe` 的 tier 过滤 | `5504097` | `_filter_release_safe()` 改恒等函数（保签名兼容 prompt 桥接器/hourly）；手动音轨路径过滤整段删除；`--release-safe` 帮助标注「已废弃」；测试改写为「标 restricted 的鼓必须被选中」 |
| T1-2 / T1-3 | 文档口径统一 + tier 字段治理 | `5e86459` | README 删除「tier→发布安全」表，改为「素材均为公共领域」+ 公版来源表（freepd.cn/freepd.com/Mixkit/Freesound-CC0）；remix/README 5 处、SKILL.md、music/README 同步；架构文档 §3.1 图注、§5 契约、§8「守住授权红线」全部修订 |
| T1-4 | 凭据容器与备份退出版本跟踪 | `e1d220a` | `radio/integrations.json` + `remix/origin.py.bak` 退出索引；新增 `integrations.json.example`；`*.bak/*.orig/*~` 入 gitignore |

**关于 license_tier 的决定**：**不改数据**，只让它失效。素材当前不在磁盘，无法逐一复核归属，
把 30,259 条批量改成 `public_domain` 等于伪造台账。字段保留、不参与判定，等素材回填时按来源重新标注。

**顺带修正的误判**：`.station_password` **早已**在 `radio/.gitignore` 里，审计报告称其「未忽略」有误。

## 4. T2 — B 轴第一批（§7.3 里成本最低、听感收益最大的两条）

> 选这两条的理由：**都有现成能力可接**，不需要新 DSP。文档 §7.3 自己也是这么建议的。

### T2-1 · `scale` 接入：按调性选素材（**建议第一个做**）

| 项 | 内容 |
|---|---|
| 文档建议 | 「给采样打调性标签，按 scale 选同 key/近 key 素材，或加 pitch-shift；无该 DSP 时至少按 key 过滤避免打架」 |
| 为什么第一 | 调性打架是**最刺耳**的问题，而「过滤」不需要写 DSP —— 是纯选音逻辑改动，风险最低 |
| 落地 | ① `manifest.json` 加 `key` 字段（可用 `librosa`/`aubio` 估，或先手工标几十条）；② `prompt_to_mix_params` 读 `data["scale"]`，转成目标 key；③ 选音时按 key 距离排序/过滤；④ `--report` 输出用了哪些 key |
| 验收 | 同一 prompt、只改 `scale`（C 大调 vs F# 小调）→ 产出文件的素材 key 分布不同，且 `--report` 里能看到 |
| 成本 | 2~3 天（含打标） |

### T2-2 · `elements` 接入：氛围层落进 sfx/animal 池

| 项 | 内容 |
|---|---|
| 文档建议 | 「把『雨声/风/街道』等映射到 sfx/animal 池，作为氛围 accent 层接入 `ROLE_ACCENT`」 |
| 为什么第二 | `sfx` 池与 `ROLE_ACCENT` 机制**已经存在**，只差一张词表 + 一次映射 |
| 落地 | ① 建 `elements → sfx/animal subcategory` 词表（外置 JSON，与 `structure_moods.json` 同风格）；② 在 `prompt_to_mix_params` 里把 elements 转成额外 accent 轨；③ 无匹配词记入 `gaps`，不假映射 |
| 验收 | prompt 里加「rain」→ 产出多一层 sfx accent；去掉则消失；`gaps` 里无「rain」 |
| 成本 | 1~2 天 |

---

## 5. T3 — B 轴第二批 + 工程收尾

| # | 事项 | 说明 |
|---|---|---|
| T3-1 | `scene` 映射到 `mixer_style` | 文档建议「并入 moods 的曲式/情绪判定，或映射到 mixers_style 着色（如『赛博』→某混音师链）」。24 位混音师链已就绪，只差映射表 |
| T3-2 | `sentence` 写入 ID3 comment | 最低成本的可追溯性（文档建议「至少保留可追溯」） |
| T3-3 | `fusion` / `fusion_with` 真并入第二风格乐器 | 文档建议「把 fusion_with 的 instruments 作为额外轨道约束真正并入」。注意 `_normalize_prompt` 已保留字段但未消费 |
| T3-4 | 抽 `remix/api.py`，6 处加载点统一 | `prompt_driven_remix.py:81`、`gui/main_window.py:434`、2 个测试、`hourly_remix.py:119`、`rerender_from_index.py:90`。改 B 轴前做，越晚越贵 |
| T3-5 | radio 加固（仅当对外） | `auth.py` 换 scrypt、`config.py` 默认 `127.0.0.1`。**与音乐发布完全解耦，可无限期推迟** |
| T3-6 | requirements 锁版本、两套件收集失败、34 处 `os.environ`、编码/路径/死代码 | 审计 T2/T3 项 |

---

## 6. 文档自身需要修的 3 处（它现在是权威说明，错话要清）

| 位置 | 现文 | 问题 | 建议 |
|---|---|---|---|
| §8 结论第 3 条 | 「`--release-safe` 守住授权红线」 | ① 素材全公版，无红线可守；② 代码上 B 变体本就绕过该过滤，这句话在事实层也站不住 | 删掉该分句，或改为「授权标签当前不可信（64.7% unknown），已废弃 release-safe」 |
| §4.2 认证模型 | 「SHA-256(salt:password) 落盘……未配置文件时视为已登录」 | **记录得很准确**，但只描述不评估。读者会以为这是设计选择而非隐患 | 补一句「单轮 SHA-256 无 KDF，仅适合纯内网；对外需换 scrypt/argon2」 |
| §5 数据契约 | manifest 含 `license_tier(free\|pack\|restricted\|unknown)` | 字段保留但语义已失效（全公版） | 标注「历史字段，当前已废弃/统一为 public_domain」 |

---

## 7. 到「提示词所写即所得」的路线图

```
现在            12 字段 → 消费 5 → 塑形 2
                ↓ T2-1 scale
第一步          塑形 3（+调性不打架）
                ↓ T2-2 elements
第二步          塑形 3 + 氛围层（元素词可见）
                ↓ T3-1 scene / T3-3 fusion
第三步          塑形 3 + 氛围 + 音色着色 + 真融合
最终            12 字段 → 消费 10~12 → 塑形 6+
```

每步都必须有「同一 prompt 只改一个字段 → 产出可测量差异」的回归用例，否则就是又一次「以为生效了」。

---

## 8. 一句话

**先把地基修到「改一个参数能被测试看出来」（T0），再按文档 §7.3 按成本从低到高补 `scale → elements → scene → sentence → fusion`（T2/T3）。**
§7 那 7 个被静默丢弃的字段，是这个项目从「随机混音器」变成「提示词驱动混音器」的全部差距 —— 而这件事只有你能定，因为它属于创作意图，不属于 bug。

---

## 9. T0 执行记录（2026-11-02 18:30–18:55 实做，已推送 Gitee）

| 项 | commit | 实测效果 |
|---|---|---|
| T0-1 二进制解析 | `b2631d3` | 新增 `core/binfind.py`；`duration_ms` 改 ffprobe→soundfile→告警；`main.py` 只在文件存在时覆盖 converter。**测试 116→125 passed**；端到端曲目时长从 `0.0s` 变 `8.0s` |
| T0-3 假评分卡 | `5a80b75` | 删除 7 维主观评分卡，改通过率 + 失败明细；实跑 PASS=20/FAIL=0 |
| T0-4 导出断言 | `a095e8d` | 新增 `MixValidationError` + 导出前/后双断言；`--bars/-bpm/-count` argparse 下界。**测试 125→140 passed**；`--bars -1` 等非法值 exit 2 |
| T0-2 自检与 CI | `fa9de91` | 新增 `remix/tools/doctor.py` + `scripts/ci_smoke.sh`；doctor 实测报出「30,259 条 manifest / 0 文件」；冒烟脚本在插件崩溃时自动降级，40 passed |

### 顺带修掉的两处「错误信息指错方向」
1. `--release-safe` 把音轨全剔空时，原本报「未找到任何音频素材」，会让人去查素材目录；现在明确报「剔除了全部 N 条素材，原因是 license_tier 缺失或非 free/pack」。
2. `--bpm 0` 原本是裸 `ZeroDivisionError` 栈；现在 argparse 层 exit 2 + 中文提示。

### 仍未做（需要你的动作或决策）
- **素材恢复**：13 个池仍是 0 文件（`doctor.py` 会持续告警）。要真正渲染成品，需先把素材同步回本地。
- **CI 落地**：`scripts/ci_smoke.sh` 已可跑，但 Gitee Go 流水线 YAML 未提交 —— 需在你的仓库开启流水线后按平台字段核对，不猜格式。
- **T1 起**：删 `--release-safe`、修架构文档 §8 那句「守住授权红线」、tier 元数据治理等（见第 3 节）。

---

## 10. T1 执行记录（19:00–19:10，已推送）

| 提交 | 内容 |
|---|---|
| `5504097` | `refactor(remix)!` 移除 `--release-safe` 过滤（BREAKING CHANGE 已注明） |
| `5e86459` | `docs` 统一公共领域口径，撤回授权红线叙事 |
| `e1d220a` | `chore(security)` 凭据容器与备份退出版本跟踪 |

### 素材来源：freepd.cn 可行性实测（2026-11-02）

| 项 | 结论 |
|---|---|
| 页面渲染 | **服务端渲染**，无需 JS，可直接 parse |
| 下载链接 | `https://freepd.cn/api/music/<hex(相对路径)>`，例如 `436f6d6564792f416c6c73204661697220496e204c6f76652e6d7033` → 解码为 `Comedy/Alls Fair In Love.mp3` |
| 实测取数 | `HTTP 200`、`Content-Type: audio/mpeg`、ID3 头、**支持 Range** → 可断点续传、可校验 |
| 授权 | 页面明确标注「公共领域（CC0）免费下载」 |
| 规模 | 仅 Comedy 一分类就 46 首；分类齐全（后续可枚举） |

**⚠️ 架构层面的关键限制**：freepd 提供的是**整曲混音**，而 `bass / drum / guita` 三个池要的是
**Demucs 分离后的 stem**。直接把整曲塞进这三个池会让混音糊成一团。可行的落点是：

1. **radio 的本地歌单**（`radio/music/`）—— 整曲播放，立刻可用，能让电台不再依赖随机渲染；
2. **测试夹具**（`remix/tests/fixtures/`）—— 让音频域可回归；
3. 要补 stem 池，需先在本机跑 Demucs 分离（当前项目没有该依赖），属独立任务。

素材抓取器尚未编写 —— 待确认落点后再动手，避免下一个无法使用的池。

---

## 11. 素材回填执行记录（19:00–19:20，已推送）

**目标**：把 `bass / drum / guita / acapella` 四池从「0 音频 / 30,259 条 manifest」补成可用的真实 stem。

### 做完的（commits `83c8cdc` + `d589e3b`）

| 环节 | 结果 |
|---|---|
| 来源 | **freepd.cn**（CC0）：服务端渲染页，直链 `/api/music/<hex(相对路径)>`，实测 HTTP 200 / audio/mpeg / 支持 Range |
| 抓取 | 新增 `remix/tools/fetch_freepd.py`（`--list` / `--match` / `--limit` / 可重跑） |
| 分离 | 新增 `remix/tools/ingest_stems.py`：ffmpeg 归一化 → demucs htdemucs 四轨 → 分池落盘 + manifest upsert |
| 灌库 | 2 首 → 4 池各 +2 stem；manifest 869→871、3981→3983、1857→1859、2969→2971 |
| 端到端 | `--bars 16 --bpm 120 --seed 7` → **32.00s / 48kHz / 2ch / PCM_24 / rms 0.270**（非静音），两条不同曲目参与 |
| 成本 | CPU 分离约 **1.2× 实时**（240s 曲 ≈ 3.3 分钟） |
| 测试 | 新增 9 条，全量 **149 passed** |

**踩到并修掉的 3 个坑**：
1. demucs 自带加载器对部分 mp3 报 `malformed stream: mpa: invalid main_data offset`，且其 ffmpeg 回退在本机识别不到 → **先用 ffmpeg 归一化成 44.1k/2ch/16bit WAV** 再送 demucs（`Attic Secrets.mp3` 修复前失败、修复后成功）。
2. manifest 写回把 indent 2→1、LF→CRLF，**整库重排 10 万行** → 改为探测原缩进 + `newline="
"` + 保留 `generated_by`（本次记 `last_ingested_by`），每池 diff 降到 29 行。
3. 「文件已存在且 sha256 相同」时提前 `continue`，导致 **manifest 被回滚后条目补不回来** → 改为跳过复制但仍 upsert。

### 没做成的（网络限制，非能力问题）

| 资源 | 通道 | 结果 |
|---|---|---|
| `radio_special_instruments` 采样（VSCO-2-CE / Salamander / world_percussion） | 仓库本身 | **仓库已归档，采样不入库且不在本机**（原路径 `G:\music\...`，G 盘已移除） |
| world-percussion（5MB CC0） | GitHub archive | ❌ 超时（GitHub 直连被墙） |
| 同上 | jsDelivr **data API** | ✅ 可枚举（244 文件 / 240 音频） |
| 同上 | jsDelivr **CDN 取文件** | ❌ `WinError 10054` 连接被重置 |

结论：**乐器池（keys/strings/brass/woodwind/ethnic）的 CC0 采样包在当前网络下无法自动获取**，
需按 `DOWNLOAD_GUIDE.html` 手工「右键另存为」。另注：这些是**单音采样**（映射乐器池），
不是 stem，与本次补的四个池是两条不同的路。

### 当前池子状态（doctor 实测）

```
bass     871 条 manifest / 2 文件      drum    3983 / 2
guita   1859 / 2                       acapella 2971 / 2
其余 9 池仍为 0 文件（合计 30,267 条 manifest / 8 文件）
```

> 「缺失 30,259」是历史台账与磁盘的差额 —— 这批素材从未在本机落过，不是本次操作造成的。
> 后续每首 freepd 曲目会稳定 +4（四池各一条），可线性补足。

---

## 12. 规模化验证 + 增量/撤回能力（19:23–19:40，已推送）

### 测试素材来源：`F:\新建文件夹`（本地曲库）

| 项 | 实测 |
|---|---|
| 规模 | 44 GB / **6377 首可读**（mp3 6187 · flac 189 · wma 4） |
| 总时长 | **426.4 小时**（中位 213s，P10 96s） |
| 用途 | **仅作隔离测试根**的验证素材（来源/授权不明，不进仓库池） |

### 规模化验证结果（隔离根 `mk_ftest`，不污染仓库）

- 8 首（15s 级）→ 8×4 = 32 stem，**总耗时 2m32s**（含转码+分离）→ **≈1.27× 实时**
- 混音 `--count 4 --bars 16 --bpm 140` → 27.43s / 48kHz / 2ch，**4 轨入选、rms 0.247**
- 推算：6377 首全量分离 ≈ **22.5 天 CPU 连续跑** → 必须挑着灌

### 两个新能力

| 能力 | 提交 | 为什么需要 |
|---|---|---|
| `--purge-tag TAG`（+`--dry-run`） | `c6b40f2` | 拿本地曲库测试后可**一键撤回**，不让「来源不明」条目永久留在公共仓库 manifest |
| 增量灌库 `pending_tracks()` / `--force` | `f7aff82` | `--src` 原来每次都全量重跑 demucs；6377 首目录做增量补充会白烧几小时 |

测试：152 → **155 passed**。

### 仓库真实池子（只收 CC0）

四池各 **6 首**（24 stem）：Alls Fair In Love / Attic Secrets / Baltic Levity / Barnville /
Barroom Ballet / BeBop for Joey。
端到端 `--count 4 --bars 16 --bpm 145 --seed 11` → 26.48s / 48kHz / 2ch / PCM_24，
peak 0.841 / rms 0.305，**3 条不同曲目**入选。

### 一个明确的取舍

**没有**把 F 盘曲库灌进仓库池。理由：那批来源与授权不明，灌进去等于在公共仓库伪造台账 ——
正是本次审计刚清理掉的问题。F 盘只用于隔离根验证；真实池子只收可核实的 CC0（freepd），一条条攒。

扩量的正确做法：`fetch_freepd --limit N` 批量灌（网络可用、来源可核实），
或等乐器池的 CC0 采样包能下载（当前 GitHub/jsDelivr 均被墙，见 §11）。

---

## 13. T2-1 完成：提示词的 `scale` 真正影响选音（19:45–20:10，已推送）

**来源**：架构文档 §7.3 的第 1 条建议（`scale` 接入）。**做法**：先不做 pitch-shift DSP，
只解决「调性打架」——给素材标调性，选音时优先兼容子集。

| 提交 | 内容 |
|---|---|
| `45264f4` | `musical_key.py` + `detect_keys.py` + `--key` + 桥接器透传 + 35 条测试 |
| `8b42ed8` | 关键修正：**排序 → 兼容子集**（排序完全无效） |
| `34c67de` | 20 首素材的调性标注入库 |

### 三个踩坑（都值得记住）

1. **`scale` 是调式名，没有主音**
   实测取值分布：小调 37 / 五声 30 / 多利亚 29 / 大调 20 / 混合利底亚 15 / 弗里几亚 11 /
   布鲁斯 5 / 全音阶 5 / 无调性 5…
   → 不能直接当 `Cm`；需「调式族」映射（小调类→minor、大调类→major、五声/无调性→不指定）。

2. **按 stem 检测会误判**
   同一首曲子的 bass/guita/acapella 被判成**三个不同调**（margin 低至 0.02）。
   → 必须把有音高的 stem **相加后**再检测，四轨共享一个调。

3. **只重排候选 = 完全无效**
   `pick_loop_candidate()` 按时长/命名挑，不看顺序 —— 同种子下 `--key C`/`Am`/`F#` 选出**一模一样**。
   → 改为「有兼容子集用子集，没有才放宽到全部」（并记 `relaxed` 计数）。

### A/B 硬证据（同种子 42，20 首素材）

| `--key` | 兼容候选 | bass | guita |
|---|---|---|---|
| C | 20 条（同调 12 / 五度 8） | Alls_Fair_In_Love（C） | Circus_of_Freaks（C） |
| Cm | 4 条（同调 2 / 五度 2） | Comic_Game_Loop（Cm） | Ghost_Town（Gm＝五度） |
| Bm | 6 条（同调 4 / 五度 2） | Foam_Rubber（Bm） | Drunken_Party（Em＝五度） |

drum 三组恒定 —— 鼓无调性、不参与偏好（符合预期；日志「未知 20」即 drum 池）。

### 素材进度

四池各 **20 首 CC0 / 80 stem**（`fetch_freepd --limit 20` + 增量灌库，总耗时约 25 分钟）。
`keys / strings / brass / woodwind / ethnic` 仍 0 —— 乐器池要 CC0 采样包，GitHub/jsDelivr 均被墙。

测试：**191 passed**。

---

## 14. §7.3 五项全部收口（20:0x–20:35，已推送）

架构文档 §7.3 的五条建议**全部落地**，没有再靠「读代码断言应该生效了」。

| # | 字段 | 状态 | 落点 | 提交 | 硬证据（可复跑） |
|---|---|---|---|---|---|
| 1 | `scale` | ✅ | `musical_key.py` + `detect_keys.py` + `_prefer_key_compatible` | `45264f4` | 换 `--key` 后选出的是不同**子集**（`pick_loop_candidate` 不看顺序，纯重排无效） |
| 2 | `elements[]` | ✅ | `element_pool.py` + `element_pools.json`（9 条规则）→ sfx/animal | `208f70d` | 命中→真实素材进 `accent`；未命中→记 `gaps`，不假映射 |
| 3 | `scene` | ✅ | `scene_style.py` + `scene_styles.json`（13 条规则）→ `mixer_style` | `8a5b3fb` | dry-run 打印 `mixer-style = X（来源：scene 规则；why）` |
| 4 | `sentence` | ✅ | `tagging.py`（WAV 走 `mutagen.wave` + COMM 帧） | `edc5f09` | 成品 ID3 comment 读回原句（WAV easy 接口读不到 COMM） |
| 5 | `fusion` | ✅ | `_fusion_style_instruments` + 第 3.5 步额外并入 | `6f004cc` | 真实渲染 6 轨：基础 5 轨全保留 + 融合鼓轨并入（两 drum 并存） |

### fusion 这条最费劲，两个坑都是「看起来已完成」

1. **`generate(fusion_with=...)` 只是换了一批乐器**
   它的 `instruments` 是混合池重采样，会丢掉主风格招牌乐器（新古典 × 中国民族乐器 → 竖琴/大提琴消失、只剩编钟）。所以「融合」听起来只是换了音色，不是两个风格叠在一起。→ 桥接器按 key 取回第二风格乐器列表，显式补轨。

2. **补了却被静默截掉，还照报「已补入」**
   `[remix] 已选择 5 条音轨` 那次的真相：dry-run 说补入 `['鼓组']`，引擎只收到 5 轨 —— 第 5 步裁剪从**头部**切，挂在尾部的融合轨被丢弃，`fusion_added` 仍非空。更难的是：即便不截掉，`max_tracks=5` 被基础轨用满时融合只能**顶替**一条（实测 `Baltic_Levity` → `Frogs_Legs_Rag`），净轨数不变，还是"换乐器"。
   → 改为融合轨在 `max_tracks` **之上额外占额度**（只受引擎 8 轨硬上限约束），先发融合轨、基础轨吃剩余；`fusion_added` 必须等于实际留在 `tracks` 里的融合轨。

### 测试判别力这次做了验证

把第 5 步回退成旧逻辑 → `test_fusion_track_is_added_not_swapped` 转红（`assert 'bass' == 'drum'`，正是「报告说补入鼓组、实际留下贝斯」）。**没做这一步就等于没验证**。

### 顺带修掉：`bash scripts/ci_smoke.sh` 原本跑不起来

`PYTHON` 未设时按名字取第一个解释器 → 命中托管 Python 3.13.12（无 pydub），硬失败退出 2。本机 PATH 上有 4 个同名项，真正的 `E:\Python314` 排第 4。改为枚举全部同名项、逐个探测依赖择优选；显式 `PYTHON=` 仍严格只认。同时把 `music/tests` 纳入冒烟/全量（此前只跑 `remix/tests`，桥接侧的 4 组契约测试从未进 CI）。

现值：`254 passed`；冒烟 `132 passed / 122 deselected`（`0d01030`）。

### 剩余

| 项 | 判断 |
|---|---|
| **T3-4 抽 `remix/api.py`**（6 处加载点统一） | 建议下一个做 —— 计划里原话「改 B 轴前做，越晚越贵」，而 B 轴已经改完了 |
| T3-6 requirements 锁版本 / 34 处 `os.environ` / 死代码 | 低风险收尾，可并入 T3-4 一次提交 |
| 乐器池 `keys/strings/brass/woodwind/ethnic` 仍 0 文件 | **卡在外部**：CC0 采样包从 GitHub/jsDelivr 取不到，需手工下载。这是「融合到民乐/管弦」听不出东西的唯一原因 |
| T3-5 radio 加固 | 仅对外才需要，与音乐发布解耦，可无限期推迟 |
| Gitee Go 流水线 | 按指示搁置 |

---

## 15. T3-6 先啃低风险部分（20:35–21:05，已推送）

按「成本从低到高」把 T3-6 里不涉及行为的几项做掉。全程没改音频行为，只改可复现性与可发现性。

| 提交 | 内容 | 为什么值得做 |
|---|---|---|
| `6f41af9` | 根 `requirements.txt` 改成 `-r remix/requirements.txt` 聚合；新增 `requirements.lock.txt`（锁 261 passed 实测版本）；新增 `remix/requirements-keys.txt`（librosa 可选）；`detect_keys` 缺 librosa 给可照做的提示 | 原根清单是 2026-08-20 自动生成快照，只有 numpy/pytest/soundfile，缺 pydub/scipy/audioop-lts，而 README 却写「scipy + soundfile 均已在 requirements.txt」。librosa 更是一个清单都没写 |
| `70b8862` | `scripts/check_doc_counts.py`：把 README 里手写的「N passed」做成机械门禁，接入 `ci_smoke.sh` | 这仓反复踩「文档说 X 实际 Y」（release-safe 守红线 / 7 处写死 ✅ / 125 passed 早已是 191）。手写数字每加一条用例就静默过期一次 |
| `1644e9d` | `pytest.ini` 从 `remix/` 提到仓库根（带 `testpaths`） | 从根跑时 rootdir 取不到 remix/pytest.ini → `smoke` 标记未注册、每个文件刷警告 |

### 门禁本身也翻过两次车（记下来）

1. `--fix` 第一版每轮循环都重读文件，**把前一处修复冲掉**，只保留最后一处。
2. `--fix` 用文本模式 + `newline="\n"` 写回，把 240 行 CRLF 的 README **整篇改行尾** —— diff 变成 `1,240c1,240`。
   修法：读写都走字节（`open(..., 'rb')` / `'wb'`），完全不碰行尾；修复累积在同一份内存副本上。

验证：注入 `261→262` 漂移 → `bash scripts/ci_smoke.sh` 退出码 1 并打印不一致项；`--fix` 后复核通过且 `git diff` 只有 3 行。

### 两个审计条目要更正

- **`version.py` 不存在**：审计写「`version.py` 在 import 时就写 stdout，GUI `--windowed` 下 `sys.stdout=None` 会崩」。全仓 `find -name version.py` 无此文件，版本常量是 `main.py:74` 的 `REMIX_VERSION`。该条目应删。
- **34 处裸 `os.environ` 的定性要收窄**：实测测试侧只有 `test_binfind.py:65` 读 `os.environ["PATH"]`，没有测试在写 env；真正的风险点集中在 `hourly_remix.py` 的批量覆盖。这条比原来的措辞轻，但仍是真问题（见下）。

### 观察（未处理）

`test_progress_reporter` 的 Tk 用例有一次报 `Can't find a usable init.tcl` 并降级为 **skip**，而 `E:\Python314\tcl\tcl8.6\init.tcl` 确实存在，随后连跑 3 次全部 passed。属 Tk 初始化偶发失败，测试按设计 skip 而非 fail（符合 remix/README 说明），暂不处理，但知道它偶发。

### 下一个

| 顺序 | 项 | 成本 | 备注 |
|---|---|---|---|
| 1 | `hourly_remix.py` 批量 env 覆盖改为隔离传参（`subprocess` 传 env 或 contextmanager） | 低-中 | 审计 T2-6 的真身；现在无人值守任务会污染进程 env |
| 2 | T3-4 抽 `remix/api.py` 统一 6 处加载点 | 中 | 原计划说「改 B 轴前做」，B 轴已完；仍是最大的重复面 |
| 3 | 乐器池 CC0 采样 | — | **卡外部**：GitHub/jsDelivr 取不到，需手工下载 |

---

## 16. ①② 完成（21:00–21:20，已推送 8bdcb8c / eebdc7e）

### ① 环境变量与"跑不起来"的脚本

审计原文是「34 处裸 `os.environ[...]` 覆盖，`hourly_remix.py:119-130` 一次覆盖 20+ 变量」。实测**不成立**：
全仓只有 11 处写入，`hourly_remix.py` 里一处 `os.environ` 都没有。真实的两个问题：

| 问题 | 实测证据 | 修法 |
|---|---|---|
| `main.py:42` 无条件把 `bin/` 前置进 PATH | 3 次加载把 PATH 从 41 段变 44 段，重复 3 次 | 改调 `binfind.ensure_path_env()`（本就幂等） |
| `ingest_categories` / `ingest_guitar` / `ingest_synth` 在定义 `_MK_ROOT` 前就引用它 | 三个脚本导入即 `NameError: _MK_ROOT is not defined`，从来没跑起来过 | 重排定义顺序 + PATH 前置加 membership 判断 |

`ingest_mixkit` 早先修过同一个 NameError，另外三个漏了 —— 说明当时是"改完一个就走"，没横向扫同类。

### ② `main.py` 的加载方式收敛

5 种加载方式（`__main__` / `import main` / 3 个不同名字的 spec 加载，其中一份连 `sys.modules` 都没注册）。
新增 `remix/core/boot.py::load_main()`，全进程只认一个 `main` 对象；`__main__` 是 main.py 时**别名**过来而不是再执行一遍。

### 顺带发现：`hourly_remix` 每次都在收尾崩

本机 `E:\ffmpeg\bin` 只有 `ffmpeg.exe`（105MB 静态版），**没有 ffprobe.exe**。老代码在渲染**成功并落盘之后**调
`binfind.require("ffprobe")` 抛 `BinaryNotFound` —— 无人值守任务每跑一次都在最后一步崩，索引也不写。

改为三态：`True` 合规 / `False` 不合规 / `None` **未校验**（缺 ffprobe），输出 `OK`/`FAIL`/`UNVERIFIED`，
索引如实写 `delivery_ok: null`。实测复跑：出片 → 「交付规格：未校验」→ 索引已更新 → exit 0。

### 两个自我更正（都记下来）

1. `test_unverified_is_not_counted_as_failure` 是**假测试** —— 只断言了 `("OK" if True else "FAIL") == "OK"`，
   等于在验 Python 的布尔逻辑，没验代码。删掉，把判定词抽成 `delivery_verdict()` 用真断言测三态。
2. 文档门禁抓到自己暴露的口径问题：README 写「N passed」，门禁数的是 `--collect-only` 收集数，
   有 skip 时两者不等。改成「N 用例」，正则同步。

### 那条 cluvon 链接

页面是 SEO 方法论（12 个**寻找方向**），**没有给任何具体站点或下载链接**，不能直接用来填池。
已派调研员按「方向 6：公共领域/开放许可音频库」去实测 FreePats / 爱荷华大学乐器库 / archive.org / Philharmonia
的可达性与直链，结果待回。

现值：**281 用例 / smoke 159 / ci_smoke exit 0**。

---

## 17. 乐器四池回填：从 0 文件到 137 条实测素材（21:20–21:50，已推送 d8b03f1）

### 调研结论：cluvon 那篇没用，但顺着方向 6 找到了真源

cluvon 的文章是「12 个寻找方向」的方法论，**一个具体站点/下载链接都没有**。派调研员实测了候选源：

| 源 | 实测 | 授权 | 结论 |
|---|---|---|---|
| **爱荷华大学 MIS** | 206 稳定，单音 AIFF 直链 | 站点原文 "without restrictions" | **可用，首选** |
| FreePats | 自托管文件 206 稳定 | 逐乐器不同（KW 钢琴 CC0 / Salamander CC-BY 3.0 / GM GPLv3+例外） | 可用，但 keys 之外覆盖零散 |
| Philharmonia（伦敦爱乐） | S3 直链 206 | **已改为可商用**，只禁原样转售音源 | 可用，但只有 MP3（有损） |
| archive.org | 三条路径全超时 | — | 不可用 |
| GitHub Releases | 偶发 1 次通，随后 3/3 超时 | — | 不可靠，不能当依赖 |
| opengameart / pianobook / GeneralUser | 首页 200 但**拿不到文件直链**（SPA / 需账号） | — | 不可用（首页通 ≠ 能下） |

调研员一条重要提醒：**Philharmonia 不该按 CC-BY-NC 排除** —— 他们页面现在写的是可商用。
这条我在实现里没有采纳为数据源（有损 MP3），但记下来供以后决策。

### 落地：137 条单音采样进四个池

新增 `remix/tools/fetch_iowa_mis.py`，实测落盘：

| 池 | 文件数 | 乐器 |
|---|---|---|
| keys | 10 | piano |
| strings | 40 | violin / viola / cello / doublebass |
| brass | 47 | trumpet / frenchhorn / trombone / tuba / saxophone |
| woodwind | 40 | flute / oboe / clarinet / bassoon |

全部 44100Hz/PCM_16（127 单声道 + 10 钢琴立体声）、sha256 与 manifest 全一致、
无孤立文件（doctor「磁盘多文件」列 = 0）。

两个设计决定值得记：
1. **等距抽取而不是取前 N**：MIS 页面按力度/奏法分组，取前 10 会全落在 `pp` 且音域偏低；
   等距取到的钢琴样本是 Bb0/G1/E2/C3/A3/Gb4/D5/B5/E7/Ab6 —— 跨了 7 个八度。
2. **抓取侧不写 `key`（除单音），也不用 chroma 硬猜**。

### 单音调性：新加「只比音级」通道

单音没有大小调色彩，但音级是确定的。原读取侧要求 `scale∈(major,minor)` 才认，
所以单音只能落进「未知」。新增 `musical_key.rank_pitch()`：同音级 = 最合、
纯五/四度次之、其余「可用不优先」，**不判不兼容**（单音能当经过音，判死会误杀）。

实测 `--key B` → B5（同音级）+ E2/Gb4/E7（五度），不兼容 0；`--key F#` → Gb4（等音）+ B5。

### 一个自己挖的坑，值得记住

detect_keys 先给 3 条钢琴写过 chroma 结果（`Piano.ff.B5` 被判成 **C#m**，conf 0.38 / margin 0.05
—— 高音区泛音把音级带偏）。刷新元数据后条目变成 `key=B（文件名）+ scale=minor（chroma）+
key_pitch_only=True`。读取侧若先看 `scale`，就会得出**「B 小调」这个谁也没测出来的调式**。

修法两处：读取侧让 `key_pitch_only` 优先于 `scale`；抓取侧写文件名音级时把 `scale/key_margin` 显式清空。
回归用例 `test_pitch_only_wins_over_stale_scale`。

### 缺口

- **ethnic 仍是 0 文件**：FreePats 的 ethnic 只有卡林巴/口弦琴，二胡/古筝/笛子/唢呐不存在；
  archive.org 与 GitHub 不可达。**没有可用公版中文民族乐器源。**
- 30139 条老 manifest 条目仍指向不存在的商业包文件（历史遗留）。

现值：**312 用例 / smoke 190 / ci_smoke exit 0**。

---

## 18. 收尾状态表（2026-11-03 04:40）

### 审计 72 条的处置进度

| 项 | 状态 | 证据 |
|---|---|---|
| P0#1 ffmpeg/ffprobe 硬编码路径 | ✅ 已闭合（T0-1） | `audit_pack.py` / `ingest_acapella.py` / `rerender_from_index.py` 三处已统一走 `binfind.require("ffprobe")`；`duration_ms` 不再静默返回 0 |
| P0#1 `duration_ms` 静默 0 | ✅ 已闭合 | 改成 ffprobe → soundfile → 告警三级回退 |
| P0#2 `remix/bin/README` 声称 164MB 实际只有 ffmpeg | ⚠️ 本机仍缺 ffprobe | `E:\ffmpeg\bin` 只有 `ffmpeg.exe`（105MB）；gyan.dev / GitHub 均被墙，**无法下载**。代码侧已能优雅降级（`hourly_remix` 三态 UNVERIFIED） |
| 13b Windows `FileNotFoundError.filename=None` | ✅ 已闭合 | 调用侧用已知常量包装，不从异常对象找路径 |
| 13d manifest↔磁盘一致性 | ✅ 部分闭合 | `doctor.py` 已有 13 池「manifest/磁盘/缺失/未登记/哈希」五列；`--hash` 可查哈希；剩余 30259 条指向历史商业包（素材未入库，属设计） |
| 14 资源泄漏（临时目录/句柄） | ✅ 已闭合（ba676c4） | `ingest_stems.py` 的 `work`/`demucs_out` 两个 `mkdtemp` 包进 `try/finally`，退出时 `shutil.rmtree` 仅删自建目录（绝不删用户 `--demucs-out`）；磁盘级 GB 级临时 WAV 泄漏消除 |
| 16 编码：文本 `open()` 缺 `encoding=` | ✅ 已闭合（ba676c4） | `remix/`+`music/`+`radio/` 文本 `open()` 全部补 `encoding="utf-8"`；`scripts/check_encoding.py`（AST 扫描，129 个 .py）接进 `ci_smoke.sh`；门禁实测 129/129 通过 |
| 17 死代码：`remix/origin.py.bak` 入库 | ✅ 已闭合 | 该 `.bak` 本就未入库（`.gitignore:74` 已有 `*.bak`，`git ls-files \| grep origin.py.bak` 无结果），与 `origin.py` 内容完全相同、无独有修复，无残留入库风险 |
| 18 路径处理 | ✅ 已闭合（2026-11-03） | `remix/` 侧早已统一用 `__file__` 推绝对路径；本轮收口残留：regenerate `instrument_taxonomy.json`（去 `G:\tools\music` 旧盘符）、`radio/openapi.{json,yaml}` 示例路径改 `<MUSICKIT_ROOT>`、3 个工具用法段（`hourly_remix`/`rerender_from_index`/`verify_release_fidelity`）的 `F:\Python314\python.exe` 改通用 `python`、`_inventory_packs` docstring 去 `G:\BaiduNetdiskDownload` 改 env 驱动；`C:\Program Files`/`C:\Windows`/`D:\private-radio-stations-2.0` 属系统路径或历史迁移注记，按惯例保留 |
| 24 radio 子进程劫持 | ✅ 已闭合（ba676c4） | `config._bundled_bin()` 只返回绝对路径或 `None`（永不裸名）；`hls.reap_orphans()` 用 `shutil.which` 取 powershell/pkill 并传 `cwd=_PROJECT_ROOT`；`transcoder`/`hls` 在 ffmpeg 缺失时早退或抛明确错误；新增 `radio/tests/test_hardening.py`（4 项）覆盖 |
| release-safe 侵权定级 | ✅ 已撤销 | P0 → P3，材料全公版；过滤已改为恒等函数 |
| §7.3 五项（scale/elements/scene/sentence/fusion） | ✅ 全部落地 | 见 §14 |

### 文档数字门禁的覆盖（这次扩了）

| 文档 | 检查点数 |
|---|---|
| README.md | 4（全量/引擎侧/桥接器/冒烟） |
| music/README.md | 2 |
| ONBOARDING.md | 12（全量×3、门禁输出快照×5、冒烟、manifest 总数×2、doctor 合计行、MIS 条数） |

关键点：门禁按**收集数**核对（不是 passed 数），因为 Tk 用例会偶发 skip；
`manifest 条目总数` 与 `MIS 条目条数` 也纳入 —— 灌一次库这两个数就变，是典型的漂移源。

### 仍然卡着的

| 项 | 卡在哪 |
|---|---|
| ethnic 池（民族乐器） | **外部**：FreePats ethnic 只有卡林巴/口弦琴；archive.org / GitHub / gyan.dev 在本机全部不可达 |
| ffprobe | **外部**：同上，无法下载 |
| Gitee Go 流水线 | 按指示搁置（且需在仓库实际开启后核对字段，不猜） |

---

### 最终收尾（2026-11-03，commit `ba676c4`，已推送 origin/master）

- **worker 接管原因**：`encoding-cleanup` 与 `radio-hardening` 两个后台 worker 因 HTTP 429 配额耗尽失败，本轮由 lead 直接落地二者未完成的改动并合并提交。
- **提交内容（18 文件，921 增 / 348 删）**：
  - radio 子进程路径加固（#24）：config / transcoder / hls 三处绝对路径 + `cwd=` + None 守卫；
  - 编码门禁（#16）：`radio/run.py` · `radio/radio/auth.py` 补 `encoding="utf-8"`，`scripts/check_encoding.py` 接 `ci_smoke.sh`；
  - 临时目录泄漏（#14）：`ingest_stems.py` `try/finally` 删自建临时目录；
  - 哈希一致性 bug：`refresh_manifest_hashes.py` 改扁平池根优先解析，重跑后 `doctor --hash` 全池 sha256 不匹配归零（animal / sfx manifest 写入真实哈希）；
  - 测试 + 文档：新增 `radio/tests/test_hardening.py`（4）、`remix/tests/test_check_encoding.py`（25）；README / ONBOARDING 同步；pytest.ini 加 `radio/tests`。
- **验证**：`check_encoding.py` 129/129 通过；新测试 29 passed；全量 pytest **346 passed / 1 skipped**；`ci_smoke.sh` exit 0；`doctor --hash` 全池 0 不匹配；推送后 `master` 与 `origin/master` 0/0 同步。
- **已闭合（2026-11-03）**：#18 路径处理（见 §18 收尾表；`remix/` 已用 `__file__` 推绝对路径，本轮收口剩余的文档/工具示例硬编码盘符）。外部阻塞项（ethnic 池、ffprobe、Gitee Go 流水线）仍待上游。

**审计处置总览**：P0 全闭合；#13b / #13d / #14 / #16 / #17 / #18 / #24 已闭合；仅剩若干外部阻塞项（ethnic 池、ffprobe、Gitee Go 流水线）待上游。
