# remix/bin — 外部工具（不纳入版本库）

`ffmpeg.exe` / `ffprobe.exe` 是 remix 流水线依赖的外部二进制，**不纳入版本库**
（两个文件合计约 164MB，与乐器池音频同样以“文本标注”方式处理）。

- 本地保留即可运行：把从 https://ffmpeg.org 下载的 Windows build 直接放入本目录即可。
- 仓库中仅以本说明文件标注其存在与获取方式，二进制依赖请就地提供。
- 若需在 CI / 新环境重建，请执行：`winget install ffmpeg` 或下载官方静态 build 解压到 `remix/bin/`。

> 与乐器池（bass/drum/guita/…）一致：实际素材/二进制不入库，仅保留 `manifest.json`
> 或本说明等纯文本标注。
