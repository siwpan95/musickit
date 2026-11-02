"""binfind — 外部二进制（ffmpeg / ffprobe）的唯一解析入口。

背景（2026-11-02 全检）：
  仓库历史上把 `remix/bin/ffmpeg.exe`、`remix/bin/ffprobe.exe` 硬编码到十余处，
  而这两个二进制被 `remix/.gitignore` 排除、从不入库。结果：新克隆必缺件，
  且不同模块解析策略不一致（有的只在 isfile 时才覆盖，有的无条件覆盖）。

本模块统一策略（与 `remix/README.md` 的说明对齐）：
  1. `remix/bin/<name>[.exe]` 存在 → 用它（项目自带优先，锁定版本）
  2. 否则 `shutil.which(<name>)` 走系统 PATH
  3. 都没有 → `resolve()` 返回 None，`require()` 抛 BinaryNotFound

调用方对于「可缺省」的场合（如 duration_ms 探测失败可降级）用 `resolve()`；
对于「缺了就必须停」的场合（如 ffmpeg 解码）用 `require()`，让错误信息带上
具体路径与安装指引，而不是 Windows 的 `[WinError 2]`。
"""
from __future__ import annotations

import os
import shutil

#: `remix/bin/` 绝对路径（本文件位于 `remix/core/`）
BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


class BinaryNotFound(RuntimeError):
    """外部二进制缺失。消息中已包含解析路径与安装指引。"""


def _exe_name(name: str) -> str:
    return name + ".exe" if os.name == "nt" else name


def resolve(name: str) -> str | None:
    """返回 `<name>` 的绝对路径；bin/ 优先，其次 PATH；都没有返回 None。"""
    if not name:
        return None
    bundled = os.path.join(BIN_DIR, _exe_name(name))
    if os.path.isfile(bundled):
        return bundled
    found = shutil.which(name)
    return found or None


def require(name: str) -> str:
    """同 resolve()，但缺失时抛 BinaryNotFound（含可操作提示）。"""
    path = resolve(name)
    if not path:
        raise BinaryNotFound(
            f"{name} 未找到：请把 {_exe_name(name)} 放入 {BIN_DIR}，"
            f"或安装到系统 PATH（Windows: winget install ffmpeg / macOS: brew install ffmpeg）"
        )
    return path


def ensure_path_env() -> None:
    """把 bin/ 前置到 PATH（幂等），便于子进程按裸名也能找到。"""
    if os.path.isdir(BIN_DIR):
        parts = os.environ.get("PATH", "").split(os.pathsep)
        if BIN_DIR not in parts:
            os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")


def status() -> dict:
    """返回两个二进制的解析结果，供 doctor / 日志使用。"""
    return {
        "bin_dir": BIN_DIR,
        "bin_dir_exists": os.path.isdir(BIN_DIR),
        "ffmpeg": resolve("ffmpeg"),
        "ffprobe": resolve("ffprobe"),
    }
