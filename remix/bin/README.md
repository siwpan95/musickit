# remix/bin — 外部工具（不纳入版本库）

`ffmpeg.exe` / `ffprobe.exe` 是 remix 流水线依赖的外部二进制，**不纳入版本库**
（与乐器池音频同样以“文本标注”方式处理；体积因 build 差异较大，单个约 60~110MB）。

> ⚠️ 本仓库**从未提交过这两个文件**（`remix/.gitignore` 排除），新克隆必定缺件。
> 缺 `ffprobe` 时 `duration_ms()` 会先退回 `soundfile`，仍失败才告警 —— 见 `remix/README.md` 环境要求。

- 本地保留即可运行：把从 https://ffmpeg.org 下载的 Windows build 直接放入本目录即可。
- 仓库中仅以本说明文件标注其存在与获取方式，二进制依赖请就地提供。
- 若需在 CI / 新环境重建，请执行：`winget install ffmpeg` 或下载官方静态 build 解压到 `remix/bin/`。

> 与乐器池（bass/drum/guita/…）一致：实际素材/二进制不入库，仅保留 `manifest.json`
> 或本说明等纯文本标注。
