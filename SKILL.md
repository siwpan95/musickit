---
name: musickit
description: Maintain the musickit phonk remix project. Real-sample mixing engine with public-domain sample governance and remix CLI. Repo root: G:/repos/musickit (override with MUSICKIT_ROOT).
agent_created: true
---

# musickit phonk 混音项目维护

## 概述
真实采样 + 本地混音引擎。素材按乐器池组织（13 池：bass/drum/guita/cowbell/synth/animal/sfx/
acapella/keys/strings/brass/woodwind/ethnic），`remix/` 负责混音，含 24 位混音师风格链与
本地流服务（mixer_radio/mixer_stream），`radio/` 是 24/7 网络电台输出端。

**新人上手**：[ONBOARDING.md](ONBOARDING.md)（环境/素材/启动/FAQ/贡献）。

## 常用命令
- 混音：`python remix/main.py --remix [--count 5 --bars 64 --bpm 140 --structure classic_drop --seed 42 --mixer-style wallace --key Am]`
- 提示词：`python music/music_prompt_generator.py -c phonk`（63 流派风格池）
- 提示词→混音：`python music/prompt_driven_remix.py -c phonk --mixer-style random`
- 24 频道流：`python remix/tools/mixer_stream.py --port 8010`（/api/channels /api/stream/<slug> /api/track/<slug>）
- 电台：`python radio/run.py`（面板/收听 :8000）
- 专辑：`python burbidge_album/build_album.py [slug]`（全量或单风格）
- 自检：`python remix/tools/doctor.py`（0 通过 / 1 告警 / 2 硬失败）
- 冒烟：`bash scripts/ci_smoke.sh`（CI 只需这一个）
- 门禁：`python scripts/check_doc_counts.py`（文档写死的用例数必须与真实一致）

## 关键约定
- 素材均为**公共领域（Public Domain）**，可自由发布、无需署名；manifest 的 `license_tier`
  是历史遗留字段，**不参与任何判定**（`--release-safe` 已于 2026-11-02 废弃，实现为恒等函数）
- **素材音频与 `remix/bin/*.exe` 均不入库**（只提交各池 `manifest.json`）；
  干净克隆约 30 MB，13 个池目录只有 manifest → 直接跑混音必报「未找到任何音频素材」
- `manifest_index.json` 不入版本库，需手动重建（`python remix/tools/build_manifest_index.py`）；
  `burbidge_album/build_index.py` **依赖它**，缺失会 FileNotFoundError
- `burbidge_album/index.json` **入库**，其 `path` 存**相对仓库根**的路径（铁律 5 去符盘）
- `MUSICKIT_ROOT` 环境变量可覆盖素材根（默认取 `remix/main.py` 的上级目录）
- `archived/` 只进不出
- Python 3.13+ 需 `audioop-lts`（标准库 `audioop` 已按 PEP 594 移除）；ffmpeg 解析顺序
  `remix/bin/` → 系统 PATH → 报错（`remix/core/binfind.py`）

## 已知陷阱
- 骨架层（drum/bass/guita）必须保底选 ≥1 小节 loop/stem，杜绝 one-shot 当唯一鼓轨
- 输出同秒冲突自动递增 _1/_2，不覆盖
- **电台端口 8000 被占用时报 `PermissionError: [WinError 10013]`** —— 那不是权限问题，
  是端口冲突（Windows 用 10013 而非 Linux 的 EADDRINUSE）；改 `radio/radio/config.py` 的 `HTTP_PORT`
- **`--key` 需先跑 `remix/tools/detect_keys.py`**，否则 manifest 无 key 字段，
  日志显示「未知 N」且各池全部放宽
- 干净克隆下 `doctor.py` 退出码为 1（素材缺失＝预期告警），不是故障；真正该警觉的是退出码 2
- 项目独立 .git（仓库根 `G:/repos/musickit`，可用 `MUSICKIT_ROOT` 覆盖）
