# G:\musickit — phonk 混音项目

## 目录结构

```
musickit/
├── bass/        # 422：258 整曲 stem（radio 分离）+ 164 短 bass loop/one-shot
├── drum/        # 725：258 整曲 stem + 467 鼓 loop/beat/one-shot
├── guita/       # 499：259 Demucs other 轨（有意当吉他/旋律轨）+ 240 真实吉他 loop
├── cowbell/     # 114：牛铃 one-shot（mp3/wav）
├── synth/       # 500：全部为真实采样（免费采样包入库，编号 51 起）
├── vocal/       # 54：动物叫声 one-shot（Mixkit，充当人声切片替代层）
├── sfx/         # 138：riser/impact/transition 过渡音效（Mixkit）
├── archived/    # 🗑️ 垃圾桶/归档区（见 archived/README.md）
├── remix/       # 混音应用（独立项目，历史：迁移自 bloodmusic/remix）
├── manifest_index.json  # 总索引：各目录 manifest + stem 编号→歌名映射
├── EVALUATION_REPORT.md # 项目评估报告（2026-08-13）
└── FIX_PLAN.md          # 修复计划与执行记录
```

## 素材约定

- `bass/drum/guita` 前 258/259 个编号文件来自 `G:\radio_music_stems` 的
  Demucs 分离 stem（歌名映射见 `manifest_index.json` 的 `stems_song_map`）；
  其后编号为免费采样包入库的 loop/one-shot。
- `bass/drum/guita` 另含编号 ≥726 的 `csmusic` 来源条目（来自 `G:\csmusic_stems`
  CS 游戏音乐分离库，由 `remix/tools/ingest_csmusic.py` 增量并入、三轨共享同一
  编号 N；歌名映射同样在 `stems_song_map` 中以 `source:"csmusic"` 标注）。
  `csmusic_stems` 仍在增⻓，新完成曲由总索引自动化每 6h 自动并入。
- `guita` = other 轨**有意**当吉他轨用，是项目约定，不是误命名。
- 各目录 `manifest.json` 记录：编号 → 来源包 → 原文件 → 授权 → 时长 → sha256。
- 采样授权：MusicRadar SampleRadar 包（royalty-free，勿转售包本体）；
  后续入库源（Signature Sounds CC0 / 99Sounds / Cymatics）见
  `archived/downloads/MANUAL_DOWNLOAD_GUIDE.md`。

## 混音（remix）

```bash
cd remix
python G:\musickit\remix\main.py --remix                    # 默认 3 轨、32 小节(~55s@140BPM)、BPM 随机
python G:\musickit\remix\main.py --remix --count 7 --bars 64 --bpm 140 --format wav  # 7 轨含 vocal/sfx
python G:\musickit\remix\main.py --remix --structure classic_drop  # 曲式模板：classic_drop/ambient_ghost/loop_stack
python G:\musickit\remix\main.py --remix --seed 42 --out output

usage: main.py [-h] [--remix] [--count COUNT] [--seed SEED] [--bars BARS] [--bpm BPM] [--structure STRUCTURE]
               [--out OUT] [--format {wav,mp3,ogg,flac}]
```

- 整曲 stem → 能量峰定位切 1~2 小节 loop；短素材循环铺满或每 2 小节点缀
- 曲式模板编排（--structure）：classic_drop/ambient_ghost/loop_stack，含**段落强度曲线**（进场/退场斜坡 + drop 增强）
- F3-v2 变速对齐：源 BPM 已知或可估计时 atempo 拉伸到目标 BPM（钳制 0.85~1.18）
- 环境变量 `MUSICKIT_ROOT` 可覆盖素材根目录
- 详见 `remix/README.md`；测试 `python -m pytest remix/tests -q`（88 passed）

## archived 定位（固化）

`archived/` 是项目的**垃圾桶/归档区**：
- 只进不出：冗余副本、机生成占位音频、下载暂存、过期素材一律移入
- 不参与混音（remix 选音不引用该目录）
- 文件可手动找回（移动而非删除，移动记录在各子目录 `_moved_*.json` /
  `remix/tools/dedupe_manifest.json`）
- 详见 `archived/README.md`
