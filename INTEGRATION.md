# musickit 双管线整合 — 固定风格 × 随机风格

G:\musickit 下有两套互补的音乐制作管线，现已通过共享模块
**burbidge_album/mixer_styles.py** 打通：随机风格决定「玩什么」，固定风格决定「谁来混」。

## 两条管线

| | 随机风格管线 | 固定风格管线 |
|---|---|---|
| 目录 | music/ + remix/ | burbidge_album/ |
| 入口 | music/prompt_driven_remix.py（桥接器）→ remix/main.py::run_remix | burbidge_album/build_album.py |
| 随机性 | 65 个流派风格池随机生成提示词（music/styles/），乐器经 instrument_taxonomy.json（242 词 → 37 类目）映射到素材池，随机选音 + 曲式模板 | 固定 6 首曲目、固定 stems 与编曲（seed 固定可复现） |
| 混音 | 分轨 RMS 归一 + 曲式编排 + 峰值归一（无调音台签名） | 24 位混音师签名链（EQ/压缩/饱和/混响/宽度/母带） |
| 运行环境 | F:\Python314（pydub + audioop-lts + numpy/scipy/soundfile） | PATH python 3.13 或 F:\Python314（numpy/scipy/soundfile） |

## 整合点：mixer_styles.py

- burbidge_album/mixer_styles.py：24 位混音师风格注册表 + bus_chain/master_chain/
  style_irs/resolve_style（burbidge/ghenea/clearmountain/marroquin/pensado/blake/lordalge/schmitt/mikedean/stent/wallace/maserati/joshua/ali/elmhirst/scheps/moulder/guzauski/albini/everett/elevado/shebib/power/zhoutianche，另支持 random）。只依赖 numpy/scipy（经 dsp.py）。
- burbidge_album/build_album.py：固定风格专辑构建器，改为从共享模块导入
  （重构后输出与重构前逐位一致，已验证）。
- remix/main.py：run_remix(..., mixer_style=None) 与 --mixer-style 参数。
  启用后：鼓/贝斯/铺垫/主奏人声分轨过对应总线链（角色→总线映射 _MIXER_ROLE_TO_BUS，
  跳过总线电平级以保留引擎编排水位），混音结果再过风格母带链
  （峰值 -1.5 dBFS 留编码余量）。不启用时行为与之前完全一致。
- music/prompt_driven_remix.py：新增 --mixer-style（slug 或 random，random 时
  每条提示词一位随机混音师，--seed 可复现），所用混音师写入 --report 的
  mixer_style 字段。

## 用法

    # 随机提示词 + 固定某位混音师
    F:/Python314/python.exe music/prompt_driven_remix.py -c phonk --mixer-style mikedean

    # 每条随机提示词随机配一位混音师
    F:/Python314/python.exe music/prompt_driven_remix.py -n 3 --fusion --mixer-style random --seed 42

    # 同一提示词 × 24 位混音师（A/B 对比）
    F:/Python314/python.exe music/music_prompt_generator.py -n 1 -c phonk --seed 7 --export json -o p.json
    F:/Python314/python.exe music/prompt_driven_remix.py --prompt-json p.json --mixer-style burbidge
    F:/Python314/python.exe music/prompt_driven_remix.py --prompt-json p.json --mixer-style ghenea
    ...（24 位依次替换）

    # remix 引擎直连
    F:/Python314/python.exe remix/main.py --remix --mixer-style blake --seed 1

    # 固定风格专辑（同一 stems × 10 位混音师）
    python burbidge_album/build_album.py            # 全部 10 风格
    python burbidge_album/build_album.py ghenea     # 单风格

## 混音师频道（Mubert 形态对齐）

- remix/tools/mixer_radio.py：本地混音师电台（--channel wallace --count 3，输出 m3u8 播放列表 + 报告）
- remix/tools/mixer_stream.py：本地流服务（http://127.0.0.1:8010/，频道主页 /api/channels /api/stream/<slug> /api/track/<slug>）
- burbidge_album/album/channels.json：24 频道目录（generate_album_docs.py 自动生成）
- 详见 MUBERT_COMPARISON.md 第五章可行性专题

## 扩展混音师

在 burbidge_album/mixer_styles.py 的 STYLES 列表里追加一个风格 dict
（slug/name/zh/color/tagline/about/refs/sig + drums/bass/pad/lead/bg/master 总线参数
+ reverb IR 参数），两条管线立即可用：专辑端重跑 build_album.py，随机端直接
--mixer-style 新slug。

## 演示输出

- music/prompt_mixes/showcase/：同一条 phonk 提示词 × 10 位混音师
  （report_<slug>.json 记录每位映射）。
- music/prompt_mixes/random_demo/：3 条融合提示词 × 随机混音师（report.json）。
- burbidge_album/album/<slug>/：固定专辑各风格成品 + 试听页（24 位混音师）。
