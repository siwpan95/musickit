# G:\musickit — phonk 混音项目（真实采样 + 本地混音引擎）

## 目录结构

```
musickit/
├── bass/          # 贝斯：整曲 stem（radio/csmusic）+ 免费包 loop/one-shot（sub_bass/808 等子类）
├── drum/          # 鼓：整曲 stem + 打击 one-shot/loop（drums_acoustic/percussion/hihat 等子类）
├── guita/         # 旋律轨：Demucs other 轨（有意当吉他轨，项目约定）+ 真吉他 loop 包
├── cowbell/       # 牛铃 one-shot（Mixkit）
├── synth/         # 合成器 loop/one-shot（SampleRadar 等，100% 真实采样）
├── acapella/      # 真人声池（Coollider Acapellas Vol.1-42 + vocal_chops 人声切片包）
├── animal/        # 动物叫声 one-shot（随机混音的人声切片替代层，不再混入人声包）
├── sfx/           # riser/impact/过渡音效（Mixkit + 采样包）
├── keys/          # 钢琴/风琴/手风琴/竖琴/钟琴（含 loop 与单音采样，单音仅作回退）
├── strings/       # 弦乐（bowed 等）
├── brass/         # 铜管/萨克斯
├── woodwind/      # 木管/笛箫（大量单音采样；旋律层选音优先 loop，见下）
├── ethnic/        # 民族乐器（拨弦/拉弦/打击）
├── archived/      # 🗑️ 垃圾桶/归档区：只进不出（见 archived/README.md）
├── remix/         # 混音应用（main.py + core/gui/utils/tools/tests + 内置 ffmpeg）
├── instrument_taxonomy.json   # 规范乐器分类体系：242 乐器词 → 37 类目 → 13 池
├── manifest_index.json        # 总索引（自动化每 6h 重建，不入版本库）
└── README.md / EVALUATION_REPORT.md / FIX_PLAN.md / MUBERT_*.md
```

## 素材授权（license_tier，写入各池 manifest.json）

| tier | 含义 | 混音默认 | --release-safe |
|------|------|---------|----------------|
| `free` | 可免费商用（Mixkit、MusicRadar SampleRadar） | ✅ 用 | ✅ 用 |
| `pack` | 商业采样包（EULA 允许音乐制作与发布成品；样本勿转售） | ✅ 用 | ✅ 用 |
| `restricted` | 商业歌曲 Demucs stem / 粉丝提取游戏音乐（仅个人练习与研究） | ✅ 用（个人用途） | ❌ 剔除 |
| `unknown` | 来源未记录 | ✅ 用（个人用途） | ❌ 剔除 |

- 授权治理脚本：`remix/tools/tag_license_tiers.py`（标注 tier + 补全 license，备份在
  `archived/manifest_backup_20260817/`）、`remix/tools/audit_licenses.py`（巡检分布）。
- **发布前请用 `--release-safe` 跑一次**：它只从 free/pack 素材选音，
  彻底避开商业歌曲 stem 与来源不明素材。

## 混音（remix）

```bash
cd remix
python main.py --remix                                          # 默认 3 轨骨架、32 小节、BPM 随机
python main.py --remix --count 5 --bars 64 --bpm 140 --format wav
python main.py --remix --structure classic_drop --seed 42 --out output
python main.py --remix --release-safe                           # 发布安全模式（仅 free/pack 素材）

usage: main.py [-h] [--remix] [--count COUNT] [--seed SEED] [--bars BARS] [--bpm BPM]
               [--structure STRUCTURE] [--out OUT] [--format {wav,mp3,ogg,flac}]
               [--release-safe]
```

**选音规则（2026-08-17 起）**：

- 骨架层（drum/bass/guita）**保底挑选 ≥1 小节的 loop/stem**（manifest 时长优先，
  未知时长则 stem 命名优先 + ffprobe 抽样探测），混音时强制循环层——
  杜绝 one-shot 被抽成唯一鼓轨导致整曲失去律动；
- 牛铃/synth/animal/sfx 为点缀层（各最多 1 条）；输出 >12 小节时按曲式模板编排
  intro→drop→outro，A/B 变体防单调；
- 整曲 stem → 能量峰定位切 1~2 小节 loop；源 BPM 已知或可估计时 atempo 对齐（钳制 0.85~1.18）；
- 输出文件名同秒冲突自动递增（`_1/_2`），不会覆盖旧产物；
- `MUSICKIT_ROOT` 环境变量可覆盖素材根目录。

测试：`python -m pytest tests -q`（**108 passed**）；快速档 `python -m pytest tests -q -m smoke`
（16 个纯逻辑用例）。Python 3.13+ 需 `audioop-lts`（requirements.txt 已含）。

## 提示词驱动混音（来自 G:\musickit\music，同仓整合）

`G:\musickit\music\prompt_driven_remix.py` 把风格提示词经
`instrument_taxonomy.json`（242 词 → 37 类目）映射为本引擎调用：

- 乐器词 → 池 + 角色：鼓/贝斯角色与引擎同口径**保底 ≥1 小节 loop**；
  旋律层（keys/strings/brass/woodwind/ethnic/guita/synth）**优先 loop/BPM 显式素材**、
  排除单音采样（如 "EHn_susDyn_..._D3"），最后才全量回退；
- 无样本/无匹配的乐器记入 `gaps`，绝不假映射；
- 曲式模板选择规则外置在 `structure_moods.json`（改词表无需改代码）；
- 支持 `--release-safe`（与引擎同口径过滤）。

## 采样源（与 license_tier 对应）\n\n| 源 | 内容 | tier |\n|----|------|------|\n| `G:\\radio_music_stems` | 商业歌曲 Demucs 分离 stem（bass/drum/guita 编号 1~258） | restricted |\n| `G:\\csmusic_stems` | CS 游戏音乐粉丝提取 stem（编号 >=726，自动化并入） | restricted |\n| `G:\\BaiduNetdiskDownload` | 商业采样包（Black Octopus/XAM/Singomakers/Loopmasters 等） | pack |\n| Mixkit / MusicRadar SampleRadar | 免费可商用素材 | free |\n\n## archived 定位（固化）

`archived/` 是项目的**垃圾桶/归档区**：只进不出、不参与混音、移动而非删除
（记录在 `dedupe_manifest.json` / `moved_vocal_packs_*.json` / `manifest_backup_*/`）。
详见 `archived/README.md`。

## 版本控制

`git`（主分支 `main`）：素材音频不入库（仅各池 `manifest.json`），
代码 / 文档 / manifest / 内置 ffmpeg 全部跟踪；修复历史见提交记录与 `FIX_PLAN.md`。
