---
name: musickit
description: Maintain the musickit phonk remix project (G:/music/musickit). Real-sample mixing engine with license-tier governance and remix CLI.
agent_created: true
---

# musickit phonk 混音项目维护

## 概述
真实采样 + 本地混音引擎。素材按乐器池组织（bass/drum/guita/acapella/sfx/keys/strings/brass/woodwind/ethnic/...），remix/ 应用负责混音，含 24 位混音师风格链与本地流服务（mixer_radio/mixer_stream）。

## 常用命令
- 混音：python G:\music\musickit\remix\main.py --remix [--count 5 --bars 64 --bpm 140 --structure classic_drop --seed 42 --mixer-style wallace]
- 发布安全：--release-safe（只用 free/pack 素材）
- 授权治理：remix/tools/tag_license_tiers.py、audit_licenses.py

## 关键约定
- 素材授权分 4 级（free/pack/restricted/unknown），发布前必须 --release-safe
- manifest_index.json 每 6h 自动重建，不入版本库
- MUSICKIT_ROOT 环境变量可覆盖素材根
- archived/ 只进不出

## 已知陷阱
- 骨架层（drum/bass/guita）必须保底选 ≥1 小节 loop/stem，杜绝 one-shot 当唯一鼓轨
- 输出同秒冲突自动递增 _1/_2，不覆盖
- 项目独立 .git（G:\music 内嵌）
