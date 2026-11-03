# musickit 全检报告（代码审查 + 安全审计 + QA 测试）

**日期**：2026-11-02
**场景**：全流程交付（代码审查 / 安全审计 / QA 测试 三线并行）
**参与成员**：产品官（gstack-product-reviewer）+ 安全卫士（gstack-security-officer）+ 质量门神（gstack-qa-lead）
**审计对象**：`D:/projects/repos/musickit`（Gitee `siwpan/musickit`，master，HEAD `f43df88`）
**规模**：113 个 `.py` / 21447 行 / 339 个 git 跟踪文件 / 13 个素材池

---

## 📌 TL;DR（执行摘要）

> **⚠️ 定级已修订 v2（2026-11-02 18:20）**：`--release-safe` 相关条目**整体撤销 P0**。素材为公版，不存在侵权风险。原 P0-1 降为 🟢 P3「建议直接删除该开关」，详见卡片下方的修订说明。**因此本报告结论从 🔴 No-Go 上调为 🟡 条件 Go。**

- **整体结论**：🟡 **条件 Go**（前置：修 ffmpeg/ffprobe 解析 + 恢复素材 + 接最小 CI）。公网暴露另需 radio 加固，但那与「发布音乐」是两条独立线。
- **真正的阻塞只剩 2 个**：① **ffmpeg/ffprobe 未入库 + `duration_ms()` 静默返回 0**（新环境 100% 跑不起来；且它会掩盖其他缺陷）；② **素材池本机为空 + 仓库零 CI**（音频域完全无法验证，112 个通过的测试全在纯逻辑层）。
- **⚠️ v3 更正（2026-11-02 18:5x）**：初稿把 `music/test_suite.py` 判为「自撰修复报告生成器、7 处写死 `✅ 修复: ✓`」——**该结论不成立，已撤回**。全仓 grep 无此字符串，`check()` 是按条件判定的真断言，`198-243` 行是 JSON/CSV 往返校验。真实问题小得多：评分卡有 3 项写死满分（功能完整性/导出可靠性/边界处理），已改为通过率统计。**教训：转述成员结论前必须自己 grep 一次原文。**
- **已撤销的一条**：`--release-safe` 的 B 变体绕过。作为**代码契约**它是真 bug（flag 与实现不符），但作为**风险**它不存在 —— 且实测该开关只放行 **31.7%** 素材（9,607/30,259），**主动砍掉 68.3%**。零收益、高摩擦，建议 retire 而非修复。
- **下一步**：81 条原始发现去重后 73 条，按 T0→T3 四档排好，见 `priority-plan-musickit-2026-11-02.md`。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟡 **条件 Go**（本地/发布均可，前置 3 项修复） ｜ 公网暴露：另需 radio 加固 |
| 严重度分布 | 🔴 2 ／ 🟠 16 ／ 🟡 25 ／ 🟢 30（去重合并后 73 条，v2 修订后） |
| 原始发现总量 | 81 条（代码 50 + 安全 22 + QA 9），合并重复 10 组 + 主理人复核新增 2 条 |
| 关键行动项 | T0 三条 / T1 四条 / T2 五条（见规划文档） |
| 音频域测试覆盖率 | **0%**（13 个池本地音频文件数全为 0，无法构造任何素材） |
| 单元测试实测 | `remix` 112 passed / 1 skipped（与 README 一致）；`music` 59 passed；**其余套件全部跑不起来或缺依赖** |
| 素材授权标签 | unknown **64.7%** / pack 26.2% / free 5.5% / restricted **3.6%** —— 与「全部公版」的事实不符，**标签本身失真** |
| 建议负责人 | ① 引擎与依赖解析：全哥 ② radio 加固：全哥（仅当要对外）③ CI/门禁：全哥（外包不了，一人团队） |

### ⚖️ 定级修订 v2：为什么撤销 release-safe 的 P0

| 项 | v1（初稿） | v2（修订） |
|---|---|---|
| 定级依据 | 代码走查发现 B 变体绕过 tier 过滤 + QA 声学实测 71.34% 能量来自 restricted 素材 | **事实前提被推翻**：素材全部为公版，`restricted` 标签本身是错的，不存在需隔离的版权素材 |
| 严重度 | 🔴 P0（发布阻塞） | 🟢 P3（建议删除功能，见规划 T1-1） |
| 后续动作 | 堵后门 + 出口断言 + 重算哈希 | **retire `--release-safe`**：删开关比修开关便宜 |
| 保留价值 | — | 证据链保留在 P3 行与 QA 产出索引中，作为「元数据失真如何误导判断」的案例 |

**数据支撑（实测）**：全库 30,259 条 —— unknown 19,574（64.7%）、pack 7,935（26.2%）、free 1,672（5.5%）、restricted 1,078（3.6%）。`--release-safe` 只放行 free+pack = **9,607 条（31.7%）**，砍掉 **20,652 条（68.3%）**。当素材全为公版时，这个比例意味着：**每三次选音有两次被一个无意义的开关挡掉。**


---

## 1. 各成员核心结论

### 🔍 产品官（代码审查，50 条：2 P0 / 6 P1 / 16 P2 / 19 P3 余）

- **核心判断**：代码「手感成熟、工程基线薄弱」。真正的设计感在 `loop_slicer` 的包络峰值扫描、`mixer_styles` 的参数化签名链、`main.py` 的曲式/变体编排上；但异常处理、资源释放、路径解析、模块加载四类问题系统性重复，且**文档与实现大面积失配**（README 8 处声称不成立）。
- **两个 P0**：
  1. ~~`--release-safe` 有后门~~ —— **v2 已撤销**（素材公版，风险前提不成立）。代码契约层面仍是真 bug，但改为「建议删开关」，见卡片下方修订说明。
  2. ffmpeg 未入库却宣称「无需系统安装 ffmpeg」，Windows 克隆态 `def test_remix_produces_output()` 断言失败。
- **最值得先修的 P1**：`remix/main.py` 被 6 个入口以 5 种不同方式加载，模块标识取决于入口 → 测试通过 ≠ 生产可用；34 处裸 `os.environ[...]` 覆盖在 GUI 下不生效（Tkinter 下 `sys.stdout` 为 `None`，而 `version.py` 在 import 时就写 stdout）。

### 🛡️ 安全卫士（OWASP + STRIDE 审计，22 条：1 P0 / 6 P1 / 8 P2 / 7 P3）

- **核心判断**：作为「离线 → 联网电台」的转型**没有配齐相应的安全设施**。静态代码看，**未发现可直接利用的高危漏洞**（无路径穿越、无命令注入、上传有 `secure_filename` + 白名单 + 流式大小上限）；但**「明文凭据入公开仓」**与**「无密码信任窗口 + 过宽默认暴露」**组合出真实风险。
- **P0（定稿前主动更正表述：不是 RCE）**：公网任何人可 clone 仓库 → 读到明文管理员密码 `.station_password`（`auth.py:23`）→ 登录控制面板 → **获得管理权限**：上传/删除音乐、改 `schedule.json`、改 `integrations.json`、开录音、切音源。这是 **A01 越权 + A07 认证失败**，不是代码执行（上传受 `_safe_filename` 剥离分隔符 + 9 种音频后缀白名单 + 落盘 `radio/music` 不在 web 根三重限制）。真正的本地执行面在别处，见 P2#24，且它**不需要公网暴露**。杀链现实：「公网 8010 开着（`config.py:20` 默认 `0.0.0.0`）+ MIT 公开仓库」。
- **P1 重点**：`verify_password()` 用**加盐 SHA-256 单次迭代**（`auth.py:87`），4 位密码可在 GPU 上秒破（应上 scrypt/argon2 或 `werkzeug.security`）；密码文件路径单一（单实例部署需 6 处共享）+ 无 `name=` 隔离 → 多实例会互相覆盖管理员密码。
- **一句给全哥的话**：`radio` 要对外，至少先把「无密码模式」的信任假设写进 README 并加显式开关，别让它成为默认行为。

### ✅ 质量门神（QA 测试，7 条：5 P1 / 2 P2）

- **核心判断**：**测试套件「部分健全、覆盖严重不均、门禁不存在」**。README 的「112 passed, 1 skipped」在 `remix/tests` 域**属实**（112+1+3 deselected = 116 collected，与 AST 静态 116 完全吻合）；但其余套件大面积跑不起来，且**没有任何自动化在跑这些测试**。
- **实测硬数字**：
  - `remix/tests` 全量：**112 passed, 1 skipped, 3 deselected**（46.30s）
  - `-m smoke`：**16 passed**（README 声称一致）
  - `music/` 三套件与根 `test_pool_plugin.py`：**59 passed**
  - `burbidge_album/test_mixer_plugin.py`：**收集失败**（`ModuleNotFoundError: No module named 'mixer_plugin'`）
  - `music/tests/test_bridge.py`：**收集失败**（`No module named 'core'`）
  - radio 侧：**0 测试、0 覆盖**（Flask/waitress/requests/mutagen 本机均未安装，纯静态核验）
  - CLI 端到端：**0/8 成功** —— `No module named 'core'`（`main.py` 把 remix/ 写进 `sys.path` 后遮蔽同名包）+ 缺 ffmpeg + 素材池空
- **~~最该警觉的~~（v3 已撤回）**：原称 `music/test_suite.py` 有 7 处写死 `✅ 修复: ✓` —— **不存在**。实际是评分卡 3 项写死满分（已修）。产出物 `TEST_REPORT.md` 已退出版本跟踪。

---

## 2. 综合审查发现（去重合并后，按严重度排序）

> 完整清单（含每条 file:line 与 PoC）见第 7 节成员原始产出索引。下表为**合并去重后的关键项**，同一问题被多人命中时只列一次并标注来源。

### 🔴 P0 — 阻塞发布（v2 修订后仅剩 2 条）

> 原 P0-1「`--release-safe` 被 B 变体击穿」已撤销定级，移至 P3（见 2 节末「已撤销条目」）。撤销理由见卡片下方「定级修订 v2」。

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 1 | 🔴 | 可运行性/文档失真 | `remix/bin/`（git 仅跟踪 `README.md`）+ `remix/core/loop_slicer.py:29-38`、`51-61`；README / remix/README / `EVALUATION_REPORT.md:77` | **ffmpeg/ffprobe 未入库，却被宣称「内置 ffmpeg 实现零外部依赖」**。`.gitignore` 排除二者；`duration_ms()` 硬编码 `_FFPROBE` 路径且失败静默 `return 0`（**当前该文件不存在 → 所有素材时长恒为 0**，`main.py:759` 的 `dur >= bar*4` 判断恒假）。新环境必跑不起来。<br>**且缺的不止一个**：`remix/bin/README.md` 自称「两个文件合计约 **164MB**」，实测目录内**只有 `ffmpeg.exe`（105,423,872B ≈ 100.5MiB），`ffprobe.exe` 从未入库**。`audit_pack.py:20`、`ingest_acapella.py:26`、`rerender_from_index.py:66` 三处硬编码 `remix/bin/ffprobe.exe` 绝对路径、无存在性校验、无 PATH 回退 ⇒ 这 3 个脚本**必然** `FileNotFoundError`。<br>**副作用**：ffprobe 缺失使每轨只切 300ms，会让「时长相关」的所有判断静默走错分支 —— 这也是多个下游怪象的共同上游 | ① README 删掉「零外部依赖 / 164MB」等失真表述，改为「需自备 ffmpeg **与 ffprobe** 两个二进制」；② `duration_ms` 失败要**显式报错或降级到 manifest 时长**，不能静默 0；③ 启动时做一次 `doctor` 自检（两个二进制 + 版本 + 素材池一致性）；④ 三处硬编码 ffprobe 的点接入统一解析入口 | 产品官 + 质量门神 + 安全卫士（收窄裸名范围时发现缺件）+ **主理人已复核文件尺寸与代码** |
| 2 | 🔴 | 质量门禁 | 全仓（无 `.github/workflows`、无 `.gitea`、无 CI 配置，仅 `radio/openapi.yaml`）；素材池 13/13 全为 0 文件 | **核心音频域零可验证性**：本机没有任何音频素材 → 选音/切片/对齐/混音/母带**全部无法运行验证**；且无 CI，唯一可跑的 `remix/tests` 全靠手动。109 个 `def test_*` 中约 41 个在音频域 | ① 建最小素材夹具仓库（3~5 个短 loop）让音频域可测；② 接 Gitee Go 或本地 pre-push 钩子跑 `-m smoke`；③ 把「素材缺失」从 skip 改为**显式失败**，别让它静默变绿 | 质量门神 + 产品官 + **主理人已复核** |

### 🟠 P1 — 发布前必修

> **⚠️ v2 提示**：本表原含「`--release-safe` 三重脆弱」证据块，因素材为公版、侵权前提不成立，已整体撤销定级并移入 2 节末「已撤销条目」。其中**仍然成立的两个事实**（tier 只按 basename 判定、83.6% 哈希过期）已并入 P1#13d，作为「素材元数据不可信」的证据保留。

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 4 | 🟠 | 认证安全 | `radio/radio/auth.py:87`、`111-116`、`138-148`、`177-181` | 密码用**加盐 SHA-256 单次迭代**（无 KDF）；`==` 非常量时间比较；**无密码模式下 `verify_password` 直接返回 True**，且 `/login` 首次 POST 即创建管理员 → 默认部署 = 零鉴权，先到者得 admin | 换 `werkzeug.security.generate_password_hash`（scrypt/pbkdf2）；用 `hmac.compare_digest`；无密码模式改为显式 `ALLOW_ANONYMOUS=1` 开关，默认关闭 | 安全卫士 + **主理人已复核** |
| 5 | 🟠 | 暴露面 | `radio/radio/config.py:20` (`HOST="0.0.0.0"`)、`radio/expose.sh`、`run.py:486,494` | 默认监听**所有网卡**，配 `expose.sh` 一键对外；而 `mixer_stream.py:246` 默认 `127.0.0.1` —— 两服务默认姿态不一致、无安全提示 | radio 默认改 `127.0.0.1`，对外需显式 `--host 0.0.0.0`；启动时打印醒目警告；加登录失败限速 | 安全卫士 + 主理人 |
| 6 | 🟠 | 凭据入库 | `radio/radio/auth.py:23`（`.station_password`）+ `.gitignore`；MIT 公开仓 | 明文管理员密码文件与 `integrations.json` 同处仓库根；一旦被 `git add -f` 或改目录即入库；公开仓等于公开凭据 | `.gitignore` 加 `radio/.station_password`、`integrations.json`；文件权限收紧；支持 env 注入 | 安全卫士 |
| 7 | 🟠 | 架构耦合 | `main.py` 被 **6 处**以 5 种方式加载：`music/prompt_driven_remix.py:81`、`gui/main_window.py:434`、`tests/test_main_selection.py:16`、`tests/test_structures.py:10`、`tools/hourly_remix.py:119`、`tools/rerender_from_index.py:90` | 模块标识取决于入口（`__main__` vs `main` vs `musickit_remix_main`）→ **测试过了不代表生产可用**、模块级状态不共享、`sys.path` 反复重排 | 抽 `remix/api.py` 作为唯一公共 API，6 处一律 `from remix import api`；`main.py` 只留 CLI 解析 | 产品官（自更正 3→6）+ 质量门神 + **主理人已复核** |
| 8 | 🟠 | 环境变量失效 | 34 处裸 `os.environ[...]` 覆盖（`hourly_remix.py:119-130` 一次覆盖 20+ 变量；`test_main_selection.py`、`test_structures.py` module 级设置） | 裸赋值覆盖、无恢复、module 级全局 → 与 `main.py:713` 在 import 时读 `MUSICKIT_ROOT` 组合出**顺序耦合**；GUI 打包（`--windowed`）下 `sys.stdout=None`，`version.py` import 时写 stdout 会崩 | 统一 `subprocess` 传 env 或 `contextmanager` 隔离；`version.py` 改为惰性打印 | 产品官（终值为 34）+ 质量门神 |
| 9 | 🟡 | 测试可信度 | `music/test_suite.py` 评分卡（原 277-296 行）；`music/TEST_REPORT.md` | **【v3 更正】** 原描述「7 处写死 `✅ 修复: ✓`」**不成立，已撤回**（全仓 grep 无此串）。真实缺陷：7 维评分卡中**功能完整性 / 导出可靠性 / 边界处理 3 项写死 10 分**，不读实际结果 → 只要脚本跑完就报「综合得分 70/70，评级 A」，会遮蔽真实失败。产出物 `TEST_REPORT.md` 已于本次退出版本跟踪 | **已修复**（commit 5a80b75）：删除主观评分卡，改为「通过率 = PASS/(PASS+FAIL) + 失败明细」，评级仅由通过率决定 | 主理人复核（产品官原始结论作废） |
| 10 | 🟠 | 构建可复现 | `radio/requirements.txt` 全部 `>=` 无上限；**根 `requirements.txt` 只有 numpy/pytest/soundfile**（缺 pydub/audioop-lts/scipy/Flask/waitress/mutagen/requests） | 无锁文件、无 hash；根 requirements 严重不足，`pip install -r requirements.txt` 跑不起 remix；本机 Flask 等**根本没装** | 三处 requirements 各自锁版本；根 requirements 补全或明确标注「仅为根级工具依赖」；提供 `requirements.lock` | 质量门神（P1）+ 安全卫士（P2，依赖审计全 UNKNOWN） |
| 11 | 🟠 | 测试无法运行 | `burbidge_album/test_mixer_plugin.py`、`music/tests/test_bridge.py` | 两个套件**收集期即失败**（`No module named 'mixer_plugin'` / `'core'`），等于这两块从没被测过 | 补 `conftest.py` 注入 `sys.path`；或改成包内相对导入 | 质量门神 |
| 12 | 🟠 | 代码正确性 | `remix/core/loop_slicer.py:51-61`、`main.py:693,719,759` | `duration_ms()` 静默吞异常返回 0 → 曲目信息打印全为 `0.0s`、变体判断恒假、按时长分支的全部分支逻辑失效 | 同 P0#2 建议②；失败要 `raise` 或回落到 manifest 时长并打日志 | 产品官 + 质量门神 + 主理人 |
| 13 | 🟠 | 静默错误 | `remix/main.py:779` 等多处 `except Exception:` 后继续 | 异常后状态不一致、B 变体静默降级为 A，产出「听起来正常但少了变化」，无任何告警 | 收窄异常类型；降级必须打 WARNING 并计入产物元数据 | 产品官 |
| 13b | 🟠 | 诊断可辨识性 | `remix/core/loop_slicer.py:60`、`radio/radio/musickit_source.py:184-186` | **Windows 下 `FileNotFoundError` 的属主不可辨认**：实测 `subprocess.run` 调不存在的 exe → `e.filename = None`、`e.argv = None`、`str(e)` 仅 `'[WinError 2] 系统找不到指定的文件。'`（还随 OS 语言变化）；只有 `open()` 才有 `e.filename`。**因此「打印 `e.filename`」这类修法在 Windows 上无效**（主理人已实测确认，见下方证据块） | **正确修法：调用侧已持有模块级常量 `_FFPROBE` / `_FFMPEG`（`loop_slicer.py:29-30`），捕获时把这个已知路径写进日志即可**，不要去异常对象里找。或在 monkeypatch `subprocess.run` 时把 `argv[0]` 记入上下文。另可 `shutil.which` 预检 | 质量门神（更正产品官建议）+ **主理人已实测** |
| 13c | 🟠 | 进程内状态污染 | `remix/gui/main_window.py:430-437` 的非 `__main__` 分支 + **`main.py:46-47` 无 `isfile` 守卫** | 已证实这是**生产运行时缺陷而非仅测试污染**：`main.py:39,46,47` **无条件**把 `_BIN_DIR` 塞进 `PATH` 并把 `pydub.AudioSegment.converter/.ffprobe` 指向 `bin/ffmpeg.exe` / `bin/ffprobe.exe`（**不检查文件是否存在**）；而同样的事 `loop_slicer.py:33-38` 是**有守卫**的。GUI 由非 `main.py` 启动时走 `import main` 分支 → 守卫被覆盖 → 用户全景下所有音频操作报「找不到 ffmpeg」 | `main.py:46-47` 加 `if os.path.isfile(...)` 守卫（与 `loop_slicer.py:35,37` 对齐）；配置改为显式参数注入，不在 import 期求值 | 质量门神 + 产品官 + **主理人已复核 `main.py:39,46-47`** |
| 13d | 🟠 | 数据一致性 | 13 个 `*/manifest.json`（共 **30,259** 条 entries）vs 磁盘现状；`stale_manifest_hashes.json`（git 跟踪）；`main.py:252-264`、`:284` | **manifest 是「按文件名查的授权与元数据索引」，但它的基准已经失效，且无一致性校验在拦**。<br>① **哈希大面积过期**：`stale_manifest_hashes.json` 记录 `checked=1869`、`stale_count=1563` → **83.6% 的 sha256 与实际文件不符**（P0#1 的第三重脆弱，见上方证据块）。<br>② **授权继承只靠 basename**：`main.py:284` `pool.get(os.path.basename(path))`，同名文件即继承 free 授权，不校验内容。<br>③ **索引与磁盘当前严重脱节**：30,259 条 entries 对应**磁盘 0 音频 / 0 子目录**（测量时刻 2026-11-02 18:15，State A，素材被 `.gitignore` 排除属设计）。<br>**【更正】** 主理人此前写「选音按 manifest 挑出不存在路径」——**错误**：选音走 `_collect_category_files()` 的 `os.walk` 磁盘枚举，manifest 只作字典查询，不会凭 manifest 造路径。真实影响是上面的 ①②③，不是「凭空选不存在的文件」 | ① `doctor` 增加 manifest↔磁盘一致性检查（缺文件即 fail-fast 列出前 N 条）；② `--release-safe` 发布流程强制重算哈希（`verify_manifest_hashes.py` 已有能力，接入即可）；③ `sync_manifests_to_disk.py` / `verify_manifest_hashes.py` 纳入 CI 或 pre-commit | 主理人实测 + 产品官（哈希弱点提示） |

> **证据块（主理人实测，2026-11-02，`E:\Python314\python.exe`）**
> ```
> subprocess.run(['remix/bin/ffprobe.exe','-version']) →
>   str(e)     = '[WinError 2] 系统找不到指定的文件。'
>   e.filename = None
>   e.argv     = None
> open('不存在的文件') →
>   str(e)     = "[Errno 2] No such file or directory: '...'"
>   e.filename = '...'          ← 只有 open() 有
> ```
> 结论：`duration_ms()` / `musickit_source` 吞掉异常后无法反查「到底缺哪个二进制」，且错误文本随 OS 语言变化，跨机器日志无法 grep。这是「排障成本」类问题，不是崩溃，故定 P1 而非 P0。

### 🟡 P2 — 建议修（25 条中择要 11 条）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 |
|---|--------|------|------|---------|------|
| 14 | 🟡 | 资源泄漏 | `remix/core/audio_loader.py`、`audio_mixer.py` 多处 tempfile/AudioSegment 未上下文管理 | 长时批量（`hourly_remix` 24/7）下临时文件累积、句柄泄漏 | 统一 `with` / `TemporaryDirectory`；异常路径也要清理 |
| 15 | 🟡 | 并发 | radio HLS 切片写与流读取、`station.py` 可变全局、Flask `threaded=True` | 无锁保护共享状态，切片切换瞬间可能读到半写文件 | 切片走「写临时名 + `os.replace` 原子改名」；共享态加 `threading.Lock` |
| 16 | 🟡 | 编码 | 多处 `open(..., "w")` 无 `encoding=`（Windows 默认 GBK 雷区） | 中文路径/元数据在非中文系统上乱码或 `UnicodeEncodeError` | 全部显式 `encoding="utf-8"` |
| 17 | 🟡 | 死代码/仓库卫生 | `remix/origin.py.bak` **被 git 跟踪**（8638B，与 origin.py 同大小） | 备份文件误入库，且与源文件同尺寸易混淆；`.gitignore` 漏掉 `*.bak` | `git rm --cached` + 补 `.gitignore`；先 diff 确认无独有修复 |
| 18 | 🟡 | 路径处理 | `os.path.join` 与字符串拼接混用；相对路径依赖 cwd | 从别处调用（GUI/计划任务）时静默找错目录 | 全量改 `pathlib.Path` + 基于 `__file__` 解析 |
| 19 | 🟡 | 文档失真 | README 8 处声称不成立（详见第 3 节） | 新人/未来的自己会被误导 | 逐条修正，把「声称」改成「实测口径」 |
| 20 | 🟡 | 安全 | `radio/radio/web.py` 上传/管理接口无速率限制、无审计日志 | 暴力破解与滥用无痕 | 加限速 + 结构化审计日志 |
| 21 | 🟡 | 安全 | 依赖全 `>=`，本机 Flask 未装却声称「可直接运行」 | 供应链与可复现性风险 | 见 P1#10 |
| 22 | 🟡 | 安全 | `mixer_stream.py:228-231` 把 `Host` 头反射进 m3u8 | Host 头注入污染播放列表 URL（低危，默认仅本机） | 用配置项或固定 `127.0.0.1:port` 生成 |
| 23 | 🟡 | 测试 | `remix/tests` 中 41/109 个用例在音频域 | 核心功能无覆盖 | 见 P0#3 |
| 24 | 🟡 | 子进程劫持 | **仅 `radio/` 两处**：`radio/radio/config.py:52-58` `_bundled_bin()` 找不到即 `return name`（裸名走 PATH）；`radio/radio/hls.py:144` 裸名调 `powershell` 且无 `cwd=` | Windows `CreateProcess` 搜索序里**当前目录优先于 System32**，故只需启动时 cwd（`expose.sh:18` 会 `cd` 到 `radio/`）内放同名文件即可劫持；`web.py:68` **import 期**就调 `hls.start()` → 不需任何 HTTP 请求即触发。<br>**修复成本极低**：全仓扫描确认 **`remix/` 侧 12 + 处全部使用绝对路径**（`audio_loader.py:26-27`、`loop_slicer.py:29-30`、`main.py:38` 等），**已建立正确约定**——把这套约定照抄到 `radio/` 这 2 处即可，无需发明新方案。原评 P3，因「同仓已有正确范例」而修复风险接近零，且 `remix/bin/README.md` 承诺 164MB 实际只有 105MB（P0#2），`_bundled_bin` 会在**看不见的情况下**静默退回裸名 → 故升 P2 | 两处改为 `shutil.which()` + 显式绝对路径候选；`hls.py` 补 `cwd=`；`_bundled_bin` 找不到时**报错而非返回裸名** | 安全卫士（收窄范围）+ **主理人已读 `config.py:52-58` 确认** |

### 🟢 P3 — 可选（30 条，摘要）

重复代码（`ingest_*` 系列脚本高度同构）、命名不一致、类型注解缺失、日志格式不统一、注释过时（`MIGRATED.txt` 内容已失效）、`build_framework.py` 生成 .bat 的转义脆弱、`archived/` 政策文档与实际移动记录未自动校验 等。

### ⚖️ 已撤销条目（v2 修订，保留证据备查）

| 原编号 | 原定级 | 撤销后 | 位置 | 保留的事实（仍成立） | 撤销理由 |
|---|---|---|---|---|---|
| 原 P0-1 | 🔴 P0 | 🟢 P3（建议删功能） | `remix/main.py:239-249` → `:707-709` → `:764-769`；`_filter_release_safe()` `main.py:270-291` | **代码层面确有此 bug**：B 变体（`bars>12`）从**未经 tier 过滤**的 `_cat_files` 随机取音，与 `--release-safe` 的契约不符；QA 声学实测 7/7 复现、71.34% 能量来自被过滤的素材；`_filter_release_safe` 本身实现正确，坏在调用链另造了绕过路径 | **前提被推翻**：素材全部为公版，`restricted` 标签失真，不存在需要隔离的版权素材。风险归零 ⇒ 只余「开关名不副实」这一契约问题 |
| 原 P0-1 之「三重脆弱」 | 🔴/🟠 | 🟡 并入 P1#13d | `main.py:284`（basename 查 tier）、`stale_manifest_hashes.json`（83.6% 哈希过期） | 授权判定只靠文件名、哈希基准大面积失效 —— **这两个事实对「素材元数据可信度」依然有效** | 但它们的危害只在「按 tier 过滤」这个动作上体现。开关一删，危害随之消失；仅剩元数据治理价值 |
| 「两 bug 互为掩体」 | 🔴 叙事 | ⚪ 归档 | `loop_slicer.py:51-61` + `main.py:776` | ffprobe 缺失 → 只切 300ms → `len(seg_b) >= bar` 拒绝变体素材，确实会掩盖变体路径的行为 | 该「掩体」掩盖的正是被撤销的那条；叙事不再作为风险论据，仅作**调试方法论**案例保留（缺依赖会让某条代码路径静默不执行） |

---

## 3. README 声称 vs 实测（契约核对）

| README 声称 | 实测 | 判定 |
|-------------|------|------|
| `pytest tests -q` → **112 passed, 1 skipped** | 112 passed, 1 skipped, 3 deselected（46.30s） | ✅ 属实 |
| `-m smoke` → **16 个纯逻辑用例** | 16 passed | ✅ 属实 |
| 「内置 ffmpeg 实现**零外部依赖**」 | git 仅跟踪 `bin/README.md`；ffmpeg/ffprobe 均未入库；本机 `ffprobe.exe` 不存在 | ❌ **失真（P0）** |
| 「`--release-safe` 只从 free/pack 选音」 | B 变体（`bars>12`）从全量目录选音，可混入被过滤的素材 | ⚠️ **契约不符（v2 降为 P3，建议删功能）** |
| 「`MUSICKIT_ROOT` 可覆盖素材根目录」 | 可覆盖，但与 34 处裸 `os.environ` 覆盖 + import 时求值组合出顺序耦合 | ⚠️ 部分成立 |
| 「输出文件名同秒冲突自动递增，不覆盖」 | 实现存在 | ✅ 属实 |
| 「Python 3.13+ 需 `audioop-lts`」 | 准确 | ✅ 属实 |
| 根 `requirements.txt` 足以安装 | 仅 numpy/pytest/soundfile，缺 pydub/audioop-lts/scipy/Flask 等 | ❌ **失真（P1）** |
| 「测试全绿 → 项目健康」 | 音频域 0 覆盖 + 无 CI（自撰报告一节已证伪，见 P1#9 更正） | ❌ **信号不可信（P0）** |

---

## ✅ 行动清单（v2 重排为 T0→T3，详见 `priority-plan-musickit-2026-11-02.md`）

| # | 行动 | 负责方 | 优先级 | 验收标准 |
|---|------|--------|--------|---------|
| T0-1 | README 删除「零外部依赖 / 164MB」，改为显式「需自备 ffmpeg **与 ffprobe**」；`duration_ms` 失败不再静默返回 0 | 全哥 | **T0** | 干净克隆 + 自备二进制后 `pytest -m smoke` 与一次 `--remix` 均成功 |
| T0-2 | 恢复素材池 + 建最小夹具（3~5 个短 loop）让音频域可测；接 CI（Gitee Go 或 pre-push 跑 `-m smoke`） | 全哥 | **T0** | CI 红灯能真实拦截；音频域至少 1 条端到端用例 |
| ~~T0-3~~ | ~~删「谎报断言」~~ → **实际执行**：改掉评分卡 3 项写死满分（原结论有误，见 P1#9） | 全哥 | ✅ 已完成 5a80b75 | 通过率统计取代主观得分；`TEST_REPORT.md` 已退出版本跟踪 |
| T1-1 | 删除 `--release-safe` 开关（或降级为可选 tier 过滤器） | 全哥 | T1 | 默认行为不再砍素材；`--remix` 全库可选 |
| T1-2 | `.gitignore` 补 `.station_password`、`integrations.json`、`*.bak`；`git rm --cached remix/origin.py.bak` | 全哥 | T1 | `git ls-files` 不再见备份/凭据 |
| T1-3 | `main.py:46-47` 加 `isfile` 守卫（对齐 `loop_slicer.py:35,37`） | 全哥 | T1 | GUI 入口不再污染全局 pydub |
| T1-4 | manifest 元数据治理：统一 `license_tier`（公版则全改 `public_domain`）或废弃该字段 | 全哥 | T1 | tier 不再产生误导；`stale_count` 归零或废弃 |
| T1-5 | 收窄 `except Exception`；降级必须告警并写入产物元数据 | 全哥 | T1 | 无裸 `except: pass` 返回 ok:true |
| T2-1 | `auth.py` 换 `werkzeug.security`（scrypt）+ `hmac.compare_digest`；无密码模式改显式开关、默认关闭 | 全哥 | T2 | 未登录访问 `/api/*` 一律 401 |
| T2-2 | `radio/config.py` 默认 `HOST` 改 `127.0.0.1`，对外需显式指定 | 全哥 | T2 | 默认只监听本机 |
| T2-3 | 抽 `remix/api.py`，6 处加载点统一改为包内导入 | 全哥 | T2 | GUI 与 CLI 走同一模块实例 |
| T2-4 | 三处 `requirements.txt` 锁版本 + 根 requirements 补全 | 全哥 | T2 | 全新 venv 一条命令装齐 |
| T2-5 | 修 `burbidge_album/test_mixer_plugin.py`、`music/tests/test_bridge.py` 收集失败 | 全哥 | T2 | 两套件可 collected |
| T2-6 | 34 处裸 `os.environ` 覆盖改隔离传参；`version.py` 惰性打印 | 全哥 | T2 | GUI `--windowed` 打包版可启动 |
| T3 | P2/P3 其余 50 余条（编码/路径/死代码/重复代码/manifest 一致性 doctor 等） | 全哥 | T3 | 见规划文档 backlog |

---

## ⚠️ 待完善 / 已知局限（读报告前请先看这段）

1. **音频域完全没有被测**。本机 13 个素材池音频文件数**全部为 0**，无法构造任何混音用例。所有「混音质量/选音正确性/切片对齐」类结论**均未经验证**，只有静态代码推断。这是本次全检最大的盲区，也是为什么 P0#3 被判为阻塞项。
2. **State A / State B 必须分开读**。审查员最初把「克隆态必失败」当作 P0 全量结论，后自行更正为：`remix/tests` 是**自包含**的（夹具在内存合成 + 临时目录，跨机器一致），**克隆态全绿真实**；但 `music/tests`、`burbidge_album`、`music/test_suite.py` 依赖真实素材池 → **克隆态必失败**。报告已按此分流。
   - **State B（真实素材）的复现方法**：准备 3~5 个短 loop（≥1 小节，free 授权）→ 按 `manifest.json` 的 schema 落进对应池子目录 → 重新导出 `manifest_index.json` → 复跑。**必须先跑夹具生成脚本**，否则 `remix/tests` 与 `music/tests` 会因夹具缺失而无法端到端复现——这是本轮 QA 的已知前置条件，不是环境意外。
   - **我原先的推断是错的，更正如下**：`manifest.json` **不是空的** —— 13 个池共 **30,259 条 entries**（`drum` 3981、`woodwind` 13179、`acapella` 2969、`strings` 2844、`keys` 2665、`guita` 1857、`bass` 869、`synth` 806、`sfx` 472、`brass` 187、`ethnic` 176、`animal` 140、`cowbell` 114）。但磁盘上 **0 个音频文件、0 个子目录**（每个池目录里仅有一个 `manifest.json`）。
   - 真实状态是「**索引完备、素材全无**」。但**影响不是「选音挑出不存在路径」**（这点我先前写错了，已更正）：选音走 `_collect_category_files()` 的 `os.walk` **磁盘枚举**，manifest 只作为「basename → 授权/时长」的**字典查询**。真正的后果是两条：① 授权继承**只靠文件名**（`main.py:284`），同名文件即继承 free 授权；② 而哈希基准本身已大面积过期（`stale_manifest_hashes.json`：1869 检查 / **1563 不符 = 83.6%**），所以「按文件名查表」这条路没有任何内容层校验兜底。详见 P1#13d。
   - 测量时刻：**2026-11-02 18:15**。素材不入库是设计要求（`.gitignore`），所以「0 音频」是**本机 State A** 的状态，不是仓库缺陷本身；缺陷在于**没有任何机制能发现索引与磁盘已经脱节**。
3. **radio 侧零动态验证**。Flask/waitress/requests/mutagen 本机均未安装，安全结论全部来自静态代码阅读，未做任何运行时验证（未发请求、未起服务）。
4. **审计期间的仓库改动（已复原两次，如实披露并指明责任方）**：`remix/bin/ffmpeg.exe`（105,423,872B，与 `E:\ffmpeg\bin\ffmpeg.exe` 同尺寸）在审计过程中**两次**被写入仓库目录 —— 18:03（首轮让音频用例跑起来）与 18:14（反事实验证期间再次恢复），均由 **QA 的环境预置**造成，与安全官无关（安全官全程只用只读命令且 `python -B`，已自查排除）。`ffprobe.exe` 始终未出现。
   - 因 `.gitignore` 排除该文件，`git status` **完全看不到** —— 属**静默环境漂移**。
   - 最终核验（18:15:56）：`remix/bin/` 仅 `README.md`、`git status` 为空、HEAD 仍 `f43df88`、素材池无残留（非 manifest 文件数全为 0）。
   - **这本身被列为一项发现**：环境预置不可见 ⇒ 同一条命令在不同时刻可能得到不同结果 ⇒ 本轮所有「实测」结论都必须带时间戳与前置条件才可复现。
5. **未做的检查**：未做渗透测试、未做性能压测、未做成品音频主观听感评估、未审计 `radio/radio-apk/` 与 PWA 前端、未跑 FFmpeg 模糊测试。
   - **「提示词字段利用率」不在本报告范围**：该主题已由 `docs/musickit-architecture.html` §7 覆盖。我复核了它的核心结论——**成立**：`generate()` 产出 12 字段（`music_prompt_generator.py:239`），`prompt_to_mix_params` 只读 5 个（`bpm`:248、`instruments`:258、`label/subgenre/moods`:313-315 仅送 `choose_structure`），`scale/elements/scene/sentence/english/fusion/fusion_with` 共 **7 字段确被静默丢弃**。优先级排期见 `priority-plan-musickit-2026-11-02.md` §4。
6. **severity 是主理人统一后的口径**。三位成员原始严重度不一致（同一问题分别被标 P0/P1/P2），第 2 节已按「影响面 × 触发概率 × 可恢复性」重新归一，可能与成员原文不同。

---

## 📚 成员产出索引（原始产出要点）

### gstack-product-reviewer（产品官）
- 共 **50 条**（46 条首发 + 5 条补充 − 1 条撤回）：**P0 2 / P1 6 / P2 16 / P3 19 余**
- P0-1 `--release-safe` B 变体后门（**v2 已撤销，见修订说明**）；P0-2 ffmpeg 未入库 + 克隆态测试断言失败
- 补充发现：`music/TEST_REPORT.md` 被跟踪且由测试脚本生成、34 处裸 `os.environ` 覆盖、6 处 `import main` 扩散面、GUI `sys.path` 重排 hack
- **关键补强**：`stale_manifest_hashes.json`（git 跟踪、459KB）显示 **1869 检查 / 1563 不符 = 83.6% 哈希过期** —— 原始用途是论证 release-safe 不可信（v2 已撤销该论点），但「元数据不可信」这一事实仍并入 P1#13d 保留（主理人已实测字段值）
- 自更正 3 处：`import main` 站点 **3 → 6**（宽模式 grep 自承命令漏了 `remix/gui/` 与跨行写法）；撤回「`e.filename` 可补路径」的修法（Windows 下 subprocess 的 filename 为 None）；修正「选音按 manifest 造路径」的误判（选音走 `os.walk` 磁盘枚举）

### gstack-security-officer（安全卫士）
- 共 **22 条**：**P0 1 / P1 6 / P2 8 / P3 7**
- **P0 是「未授权管理员访问 + 可抢占账户」，不是 RCE**（安全官定稿前主动更正了自己的表述）：拿到的是上传/删除音乐、改 `schedule.json`、改 `integrations.json`、开录音、切音源 —— 属 A01 越权 + A07 认证失败。**上传受三重限制**（`_safe_filename` 剥离 `/ \`、`_allowed_file` 只放行 9 种音频后缀、落盘 `radio/music` 不在 web 根且无路由服务它），因此**够不到代码执行**。
- **两条杀链必须分开看，前置条件不同**：①「已知密码 → 登录」需 `.station_password` 已存在；②「无密码 → 首个 POST 即设管理员」需该文件不存在；③ 真正的本地代码执行面是 `config.py:52-58` / `hls.py:144` 的**裸名子进程劫持**，它**不依赖公网暴露**、本地启动即触发。混成一句会让 owner 修完 ① 以为 ③ 也关了（见 P2#24）。
- **范围收窄（对 owner 有利）**：全仓扫描确认 `remix/` 侧 12+ 处**全部使用绝对路径**（正确约定），裸名面**只有 `radio/` 2 处** → 修复是「照抄同仓既有约定」，不是发明新方案。
- **P1**：SHA-256 单次迭代无 KDF、`verify_password` 无密码即 `True`、密码文件单点路径无实例隔离、`expose.sh` 无任何提示、缺速率限制、依赖全 `>=` 无上限。
- **明确结论**：**静态未见路径穿越 / 命令注入 / 上传绕过**（`secure_filename` + 白名单 + 流式大小上限均到位）。风险性质是「加固缺失 + 暴露面过宽」，不是「有洞」。
- 自查排除：`remix/bin/ffmpeg.exe` 的出现与安全官无关（全程只读命令 + `python -B`，无 `cp`/`pip`/`curl`）；实际由 QA 环境预置造成。

### gstack-qa-lead（质量门神）
- 共 **7 条**：**P1 5 / P2 2**
- 实测：`remix/tests` 112 passed / 1 skipped / 3 deselected（46.30s，与 README 一致，116 collected = AST 静态 116）；`-m smoke` 16 passed；`music/` + 根 `test_pool_plugin.py` 59 passed
- 失败：`burbidge_album/test_mixer_plugin.py`、`music/tests/test_bridge.py` 收集期失败；radio 侧 0 测试
- CLI 端到端 **0/8**：`No module named 'core'`（`sys.path` 遮蔽）+ 缺 ffmpeg + 素材池空
- **实证（方法论值得保留，结论已于 v2 撤销）**：用 4 条诱饵素材（3 条 restricted、振幅 0.3 vs 正常素材 0.001）做反事实验证，`--release-safe --bars 16` 连跑 → 7/7 命中被过滤素材、占输出能量 71.34%（基线 0.0644%）。**该实验证明了「开关不按其声称工作」这个代码事实**；至于是否构成风险，取决于素材授权，而素材为公版 ⇒ 风险不成立
- **发现两 bug 互为掩体**：缺 ffprobe 时每轨只切 300ms，`len(seg_b) >= bar` 恰好拒掉违规素材 → 漏洞在开发机永不可见
- 实测否决产品官的 `e.filename` 修法（Windows 下为 `None`），并给出正确落点（调用侧用已知常量包装）
- 单列「环境预置与可复现性」一节，如实交代 ffmpeg 两次写入与清理

---

## 附录 A · State B（真实素材）复现夹具配方

> 目的：让「依赖素材池的套件」从**跑不起来**变成**可复现**。这是 P0#3 的落地步骤，照抄可跑。

```bash
cd D:/projects/repos/musickit

# 1) 造 4 个短 loop（≥1 小节，BPM 120 时 1 小节 = 2s）。用 ffmpeg 合成 sine/噪声即可，纯占位
#    注意：remix/bin/ffmpeg.exe 当前不存在，这里用系统 PATH 上的 ffmpeg；若已补入 bin/ 也可换回
mkdir -p _fixture/{drum,bass,guita,cowbell}
FF="ffmpeg"                    # 或 "E:/ffmpeg/bin/ffmpeg.exe"
for pair in "drum:200:noise" "bass:80:sine" "guita:440:sine" "cowbell:900:sine"; do
  cat=${pair%%:*}; rest=${pair#*:}; freq=${rest%%:*}; kind=${rest##*:}
  src="sine=frequency=${freq}"; [ "$kind" = "noise" ] && src="anoisesrc=color=white"
  "$FF" -y -f lavfi -i "$src:duration=8" -ac 2 -ar 44100 \
    "_fixture/${cat}/${cat}_loop_01.wav"
done

# 2) 按 manifest 的 schema 注册（entries 至少含 file 字段；license_tier 必须 free 才过 release-safe）
E:/Python314/python.exe - <<'PY'
import json, os, pathlib
for cat in ("drum","bass","guita","cowbell"):
    p = pathlib.Path(cat)/"manifest.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"entries": []}
    d.setdefault("entries", [])
    d["entries"] = [e for e in d["entries"]
                    if not str(e.get("file","")).startswith(f"{cat}_fixture")]
    for f in (pathlib.Path("_fixture")/cat).glob("*.wav"):
        d["entries"].append({"file": f"{cat}_fixture_{f.name}",
                             "license": "self-generated",
                             "license_tier": "free",
                             "duration_ms": 8000,
                             "kind": "loop"})
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    # 实体文件落到池目录，文件名与 manifest 的 file 字段对齐
    for f in (pathlib.Path("_fixture")/cat).glob("*.wav"):
        (pathlib.Path(cat)/f"{cat}_fixture_{f.name}").write_bytes(f.read_bytes())
print("fixture ok")
PY

# 3) 重建总索引（生成物，已 .gitignore）
E:/Python314/python.exe remix/tools/build_manifest_index.py

# 4) 此时才可跑依赖素材的套件与 CLI
cd remix && E:/Python314/python.exe -m pytest tests -q
E:/Python314/python.exe main.py --remix --count 1 --bars 8 --bpm 120 --format wav --seed 42 --release-safe
```

**注意**：① 夹具是**自造正弦/噪声**，只验证「管线能跑通」，**不验证音质**；② `license_tier` 必须写 `free`，否则 `--release-safe` 会正确地把它们全部剔除（那正好可当反向用例）；③ 用完删 `_fixture/` 与各池 `*_fixture_*` 文件，别提交进库。

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。
> 报告内所有 `file:line` 均基于 HEAD `f43df88`，复核时请确认该提交未被改写。
