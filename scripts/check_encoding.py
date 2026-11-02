#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_encoding —— 文本模式的文件打开必须显式写 encoding="utf-8"。

为什么需要：
  Windows 上 `open()` 默认用 locale 编码（简体中文 Windows 是 GBK/cp936）。
  一旦文件内容含中文（中文路径、素材标题、ID3 注释、manifest 里的中文 license
  文本），轻则写出乱码，重则 `UnicodeEncodeError` 直接崩。
  这类 bug 在开发机上（UTF-8 locale）不复现，一到别人机器上就炸，
  所以必须靠机械门禁兜住，而不是靠人记得写。

检查对象：
  remix/**/*.py、music/**/*.py、radio/**/*.py  —— 所有文本模式的文件打开

命中规则（故意保守，宁可漏报也不误报 —— 误报的门禁没人会用）：
  1. 只看「能确定是文本模式」的打开：
     · `open(...)`（内建）、`io.open(...)`
     · `Path(...).open(...)`        —— mode 是**第一个**位置参数
     · `Path(...).read_text(...)`  —— 等价于 open(mode="r")
     · `Path(...).write_text(...)` —— 等价于 open(mode="w")
  2. mode 是字符串字面量时，含 `b` 视为二进制（rb / wb / ab / rb+ / w+b ...）→ 跳过；
     mode 缺省时按默认的 `"r"` 处理（文本）→ 要查。
  3. mode 不是字面量（拼出来的变量等）→ 无法判定，跳过（不猜）。
  4. 已经显式给了 `encoding=` → 通过。
  5. 二进制模式下 `encoding=` 本来就非法，所以二进制永远不报。

退出码：0 干净 / 1 有命中

用法：
  python scripts/check_encoding.py
  python scripts/check_encoding.py --verbose     # 附带扫描统计
"""
from __future__ import annotations

import argparse
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ("remix", "music", "radio")


# ---- 二进制模式里带 'b'；二进制下加 encoding 本来就是非法用法 ----
def _is_binary_mode(mode: str) -> bool:
    return "b" in mode


def _literal_str(node: ast.AST) -> str | None:
    """只有字符串字面量才算数；拼出来的表达式一律当作「判不出来」。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_path_call(node: ast.AST) -> bool:
    """node 是不是 Path(...) / PurePath(...) / pathlib.Path(...) 这类构造。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in ("Path", "PurePath"):
        return True
    if isinstance(func, ast.Attribute) and func.attr in ("Path", "PurePath"):
        return True
    return False


def _open_calls(tree: ast.AST) -> list[tuple[ast.Call, str]]:
    """挑出所有「文件打开」调用点，返回 [(call, kind)]。

    kind 说明这个调用点的 mode 参数在哪个位置（0 = 第一个位置参数，1 = 第二个）。
    内建 open(file, mode='r', ...) 的 mode 是第 2 个；Path.open(mode='r', ...) 是第 1 个。
    """
    out: list[tuple[ast.Call, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # 内建 open(...)
        if isinstance(func, ast.Name) and func.id == "open":
            out.append((node, "1"))
            continue

        if isinstance(func, ast.Attribute):
            # io.open(...)：与内建同签名
            if func.attr == "open" and isinstance(func.value, ast.Name) \
                    and func.value.id == "io":
                out.append((node, "1"))
                continue

            # Path(...).open(...) / .read_text(...) / .write_text(...)
            if func.attr in ("open", "read_text", "write_text") \
                    and _is_path_call(func.value):
                if func.attr == "open":
                    out.append((node, "0"))      # Path.open(mode='r', ...)
                else:
                    out.append((node, "text"))   # read_text/write_text：恒为文本
                continue

    return out


def _has_encoding_kw(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _mode_of(call: ast.Call, kind: str) -> str | None:
    """取 mode；返回 None 表示「判不出来，应跳过」。"""
    if kind == "text":
        return "w"                      # read_text/write_text 恒为文本模式

    mode_arg = None
    if kind == "0":                     # Path.open(mode='r', ...) —— mode 是第 1 个位置参数
        if len(call.args) >= 1:
            mode_arg = call.args[0]
        else:
            for kw in call.keywords:
                if kw.arg == "mode":
                    mode_arg = kw.value
                    break
    else:                               # 内建 open(file, mode='r', ...)
        if len(call.args) >= 2:
            mode_arg = call.args[1]
        else:
            for kw in call.keywords:
                if kw.arg == "mode":
                    mode_arg = kw.value
                    break

    if mode_arg is None:
        return "r"                      # 默认文本模式
    lit = _literal_str(mode_arg)
    if lit is None:
        return None                     # 判不出来 → 不猜、不报
    return lit


def scan_source(source: str, filename: str = "<source>") -> list[tuple[int, str]]:
    """扫一段源码，返回 [(行号, 说明)]；为空表示干净。"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []                        # 语法错误由别处报，本门禁不重复报

    hits: list[tuple[int, str]] = []
    for call, kind in _open_calls(tree):
        if _has_encoding_kw(call):
            continue
        mode = _mode_of(call, kind)
        if mode is None:
            continue                     # 判不出来 → 不猜、不报
        if _is_binary_mode(mode):
            continue                     # 二进制：加 encoding 本来就非法
        hits.append((call.lineno, f"文本模式 open(mode={mode!r}) 缺 encoding="))
    return hits


def scan_file(path: str) -> list[tuple[int, str]]:
    """扫一个文件，返回 [(行号, 说明)]。"""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []                        # 不是 UTF-8 的源码，不归本门禁管
    return scan_source(source, filename=path)


def iter_py_files(root: str, top: str) -> list[str]:
    base = os.path.join(root, top)
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="检查 remix/ 与 music/ 下文本模式 open() 是否显式指定 encoding")
    ap.add_argument("--verbose", action="store_true", help="打印扫描统计")
    ap.add_argument("--root", default=ROOT, help="仓库根目录（默认取脚本所在仓库）")
    args = ap.parse_args()

    total_files = 0
    total_hits = 0
    report: list[str] = []

    for top in SCAN_DIRS:
        files = iter_py_files(args.root, top)
        total_files += len(files)
        if args.verbose:
            print(f"扫描 {top}/：{len(files)} 个 .py")
        for path in files:
            hits = scan_file(path)
            if not hits:
                continue
            rel = os.path.relpath(path, args.root).replace("\\", "/")
            for lineno, why in hits:
                total_hits += 1
                report.append(f"{rel}:{lineno}: {why}")

    if report:
        print("❌ 文本模式 open() 缺 encoding=（Windows 上默认 GBK，会写出乱码/抛 UnicodeEncodeError）：")
        for line in report:
            print("   " + line)
        print()
        print(f"共 {total_hits} 处。修法：给 open() 补 encoding=\"utf-8\"（二进制模式不要加）。")
        return 1

    print(f"✅ 文本模式 open() 均已显式指定 encoding（扫了 {total_files} 个 .py）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
