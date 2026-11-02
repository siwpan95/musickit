# docs/ — 文档归类区

本目录集中存放 musickit 的**说明性文档**。根目录只保留「新人第一眼要看的」与
「运行时必须留在根的」两类文件。

## 目录

### 核心设计（先读这些）

| 文件 | 内容 |
|------|------|
| [musickit-architecture.html](musickit-architecture.html) | **架构设计文档**（HTML）。§7 列出「提示词 12 字段只消费 5 个」的能力缺口，是能力补全路线图的源头 |
| [INTEGRATION.md](INTEGRATION.md) | 双管线整合总览：固定风格（burbidge_album）× 随机风格（remix）如何经 `mixer_styles.py` 打通 |
| [../README.md](../README.md) | 仓库总览（功能、素材授权、命令） |
| [../ONBOARDING.md](../ONBOARDING.md) | **新人开发上手指南**（环境/获取/素材/启动/FAQ/贡献） |

### Mubert 对照线（2026-08 的调研产物）

| 文件 | 内容 |
|------|------|
| [MUBERT_RESEARCH.md](MUBERT_RESEARCH.md) | 调研报告：Mubert 能否帮上忙 |
| [MUBERT_METHODOLOGY.md](MUBERT_METHODOLOGY.md) | 方法论移植：不接 Mubert，学它的设计思想（结构模板化） |
| [MUBERT_COMPARISON.md](MUBERT_COMPARISON.md) | 对比报告：固定风格 × 随机风格的双轴对照；混音师频道可行性专题（L1~L4） |

### 历史评估与计划（存档性质）

| 文件 | 内容 |
|------|------|
| [EVALUATION_REPORT.md](EVALUATION_REPORT.md) | 项目评估报告（2026-08-13）：素材逐目录实测、选音粒度问题 |
| [FIX_PLAN.md](FIX_PLAN.md) | 修复计划 v2：按 P0→P2 排期，附 2026-08-17 整改记录 |
| [深度评估_20260817.md](深度评估_20260817.md) | 与 `G:\tools\music` 的深度评估（2026-08-17） |
| [深度评估_更正_20260817.md](深度评估_更正_20260817.md) | 上文的勘误（乱码文件，以本篇为准） |
| [RADIO_MERGE.md](RADIO_MERGE.md) | radio 并入 musickit 的合并说明（2026-09-02 从历史还原） |

### audits/ — 巡检快照

一次性巡检工具的历史输出，保留作追溯用，**非运行时依赖**：

| 文件 | 来源工具 | 内容 |
|------|---------|------|
| [audits/dedupe_report_20260817.json](audits/dedupe_report_20260817.json) | `remix/tools/dedupe_scan.py` | 13 池判重结果（含跨池重复组） |
| [audits/dedupe_report_20260818.json](audits/dedupe_report_20260818.json) | 同上 | 第二轮判重快照 |
| [audits/license_audit.json](audits/license_audit.json) | `remix/tools/audit_licenses.py` | 各池 license_tier 分布（历史字段，现已不参与判定） |
| [audits/stale_manifest_hashes.json](audits/stale_manifest_hashes.json) | `remix/tools/verify_manifest_hashes.py` | 与磁盘不符的 manifest 条目清单 |

> 这些快照反映的是 **2026-08-18** 时的素材状态。素材已多次回填与清理，
> 数字不再代表当前 —— 现状用 `python remix/tools/doctor.py` 实测。

## 根目录为什么还留着一堆文件

以下文件**必须留在仓库根**，移动会直接打断运行时或打包链：

| 文件 | 约束来源 |
|------|---------|
| `instrument_taxonomy.json` | `music/prompt_driven_remix.py` 按仓库根读取（乐器词 → 池 → 角色映射表） |
| `pool_plugin.py` | `build_framework.py` 按**文件名**从根拷贝；`test_pool_plugin.py` 与它同目录 `import` |
| `test_pool_plugin.py` | 同上（`from pool_plugin import ...`） |
| `build_framework.py` | `MUSICKIT = Path(__file__).resolve().parent`，且按根找 `musickit-framework.iss` |
| `musickit-framework.iss` | Inno Setup 用 `SourcePath` 相对定位，必须与 `build_framework.py` 同级 |
| `快速步骤.bat` | 用 `%~dp0` 定位 `remix\main.py`，`%~dp0` = 脚本所在目录 |
| `manifest_index.json` | 总索引，不入版本库；由 `remix/tools/build_manifest_index.py` 重建 |

`requirements*.txt` / `pytest.ini` / `SKILL.md` / `LICENSE` 属常规根文件，不在此列。

## 文档与代码不一致时怎么办

本目录是**说明性文档**，代码是**事实源**。两者冲突时：

1. 以代码实测为准（跑 `python remix/tools/doctor.py`、`bash scripts/ci_smoke.sh`）；
2. 修正文档，并把修正写进提交信息 —— 数字类内容由
   `python scripts/check_doc_counts.py` 做机械门禁，不靠人记。
