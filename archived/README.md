# archived/ — 垃圾桶（归档区）README

> 定位固化（2026-08-13）：本目录是 musickit 的**垃圾桶/归档区**，
> 原名为 `.pass`，后按项目约定改名 `archived`。

## 政策（只进不出）

1. **只进不出**：冗余副本、机生成占位音频、下载暂存、过期素材一律移入此处，
   正常流程下不再从本目录取用。
2. **不参与混音**：`remix` 的选音目录只有 bass/drum/guita/cowbell/synth，
   本目录永远不会被混音管线引用。
3. **移动而非删除**：所有进入本目录的文件都是 `move` 进来的，
   移动记录见各子目录的 `_moved_*.json` 或 `remix/tools/dedupe_manifest.json`，
   需要找回时按记录逆向 move 即可。
4. **可清空**：确认不再需要时，本目录内容可以整目录删除（只影响归档，不影响项目）。

## 当前内容

| 子目录 | 内容 | 时间 |
|--------|------|------|
| `1 (1)~1 (40).wav`（根） | 历史遗留占位音频（原 .pass 内容，40 个） | 2026-08-13 前 |
| `dedupe_cowbell/` | cowbell 去重移入的 60 份重复拷贝 | Phase 1 |
| `dedupe_synth/` | synth 去重移入的 27 份重复拷贝 | Phase 1 |
| `synth_placeholder/` | synth 机生成占位音频 23 个（被真实采样替换） | Phase 2 |
| `downloads/` | 采样包下载暂存 + 解包目录 + 手动下载指南 | Phase 2 |

`downloads/` 例外：它是**下载暂存区**（新包先放这里审计，再入库到素材目录），
用完的 zip 与解包目录可随包入库后清理（见 `downloads/MANUAL_DOWNLOAD_GUIDE.md`）。
