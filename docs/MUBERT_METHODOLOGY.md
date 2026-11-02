# Mubert 方法论移植 —— 不接 Mubert，学它的设计思想

> 背景：Mubert 调研结论是「当素材源用价值有限（分轨不可导出、与真实采样路线冲突）」，
> 但它作为**音乐基础设施的方法论**值得系统学习。本文提炼其方法论，逐条映射到
> musickit 自有流水线（真实采样 + 本地代码），能落地的直接落地。

---

## 一、方法论提炼（Mubert 真正值得学的东西）

| # | Mubert 方法论 | 本质 | musickit 映射 |
|---|--------------|------|--------------|
| M1 | **四种产品形态**：track / jingle / loop / mix | 把「曲式结构」做成可复用的产品模板（jingle = intro-break-drop-outro） | 曲式模板库（本回合落地） |
| M2 | **分层茎轨架构**：drums / bass / leads / vocals / effects | 每层有固定角色 + 进入时机 + 强度 | 素材目录→角色映射（已有雏形） |
| M3 | **Quick Remix 茎轨替换**：同编排换茎轨 = 新版本 | 编排与素材**完全解耦**，模板不变、素材可换 | A/B 变体（已有）→ 升级为模板+素材池彻底分离 |
| M4 | **intensity 参数**（high/medium/low） | 段落强度是显式参数而非隐含结果 | 分轨增益表（已有）→ 段落强度曲线（v2） |
| M5 | **一致性引擎**（同参数→风格一致，不同种子→新鲜感） | 生成的可复现性 | `--seed` 复现（已有） |
| M6 | **duration 参数化**（15s~25min 任意） | 时长是第一参数 | `--bars N`（已有） |
| M7 | **API 化管线**（10 秒出一曲） | 流水线全自动化 | 本地 CLI 12.8s/曲（已有） |

**核心方法论一句话**：*把"结构模板"和"素材池"彻底分离——模板决定骨架与呼吸感，素材决定音色与新鲜感，两者各自可换可复现。*

---

## 二、现状对照

| 能力 | 现状 | 差距 |
|------|------|------|
| 曲式模板 | main.py 硬编码一套段落（intro 4/bass 4/cowbell 6/synth 8/outro 4） | 只有一套，且写死在代码里 → **本回合外置为 JSON 模板库** |
| 茎轨角色 | 目录已映射 drum/bass/guita/cowbell/synth | guita 层实为 other 轨充当吉他 → **本回合补真实吉他** |
| 编排-素材解耦 | A/B 变体雏形（同曲两段/同类两文件） | 模板不可选、素材池未池化 → 模板外置后自然达成 |
| intensity 曲线 | 单表分轨增益 | 段落级强度变化（drop 更狠）→ v2 |
| 人声切片层 | 无（用户裁定：可用动物叫声替代，不必须人声） | 路线图：BBC Sound Effects 动物叫声 / 99Sounds Nature |

---

## 三、本回合落地：曲式模板库（M1 + M3）

新增 `remix/templates/structures.json`，每个模板 = jingle 式结构配方：

```jsonc
{
  "classic_drop": {              // 经典 phonk：intro → 层层叠加 → outro
    "min_bars": 13,
    "intro_bars": 4, "outro_bars": 4, "fade_out_bars": 2,
    "layers": {                   // 负数 = 距结尾偏移
      "drum":  [0, -1], "guita": [0, -1],
      "bass":  [4, -4], "cowbell": [6, -4], "synth": [8, -4]
    }
  },
  "ambient_ghost": {             // 氛围向：旋律先行，鼓后半段才进
    ...
  },
  "straight_loop": {             // 全铺平循环（短曲 fallback）
    ...
  }
}
```

`main.py` 增加 `--structure NAME`（默认从模板库随机选一套）：
- 同一模板 + 不同 seed = 同骨架不同素材（M5 一致性思想的模板级复现）
- 同一 seed + 不同模板 = 同素材不同骨架（M3 解耦的直接证明）
- 模板不足 `min_bars` 时自动退化为全铺平（straight_loop）

## 四、本回合落地：真实吉他音轨（补 guita 层）

现状：`guita/` 259 个文件全部是 Demucs **other 轨**（用户有意当吉他/旋律轨用），
没有一根真正的吉他。本回合从 MusicRadar SampleRadar 补两个免费包：

| 包 | 内容 | 授权 |
|----|------|------|
| 272 Guitar & Bass Samples | 吉他 loop（管压/哇音/Guitar Rig 处理）+ 贝斯 loop，按 tempo 分目录 | royalty-free |
| 188 Processed Guitar | Strat/Tele/Gretsch 过效果器链的暗色吉他线（24-bit） | royalty-free |

入库方式：走既有 audit + 归一化流水线，编号从 260 续接进 `guita/`，
manifest 记录来源。之后 guita 池 = 259 other 轨（当吉他用的旋律层）+ N 根真吉他 loop，
`--remix` 随机选到哪个用哪个，A/B 变体自动覆盖。

## 五、其他层的「其他方法」路线图（非 Mubert）

| 层 | 替代方法 | 来源候选 |
|----|---------|---------|
| 人声切片替代（动物叫声/音效点缀） | 免费音效库 | BBC Sound Effects（33,000 剪辑，含 Natural History Unit 15,000 条动物实录，RemArc 协议可下载）；99Sounds Nature Sounds / World Sounds |
| SFX riser/impact 过渡层 | 免费 SFX 包 | 99Sounds Sound Design Tools（360 个，含 riser/impact/glitch）；MusicRadar FX 类 SampleRadar 包 |
| 编排结构基准 | 人工听感基准 | Mubert 官网公开试听（免费）＋经典 phonk 曲目人工拉片（无需 API） |
| 变体素材扩充 | 继续免费采样包 | 每月 SampleRadar 新包例行入库（已有 audit+ingest 流水线直接复用） |

## 六、结论

不接 Mubert API 也能拿到它的方法论红利：
1. **曲式模板库**（M1/M3/M5）——结构配方外置、可换可复现；
2. **真吉他补充**（M2 补缺）——让 guita 层名副其实；
3. **强度曲线 / 动物叫声点缀 / SFX 层**——后续用免费素材按路线图补，成本为零。

musickit 的最终形态与 Mubert 的差异恰恰是优势：**结构学它（模板化），素材用自己的（真实采样），管线留在本地（零 API 成本、可导出真分轨）**。
