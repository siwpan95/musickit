#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""一次性数据修补（在补丁包 apply 时由 apply_patch.ps1 调用）：

1. validate_styles.py：清理死条件表达式

（注：styles/phonk.json 的「轻冯/重冯」是用户确认的有意风格分类（冯=phonk），
此前的重命名方案已按用户澄清撤销。）
"""
import os
import sys

MUSIC_DIR = os.path.dirname(os.path.abspath(__file__))


def fix_validate_styles() -> None:
    p = os.path.join(MUSIC_DIR, "validate_styles.py")
    with open(p, encoding="utf-8") as f:
        t = f.read()
    old = (
        '        status = "\u26a0\ufe0f" if (missing or warnings and False) else "\u2713"\n'
        "        if missing:\n"
        '            status = "\u274c"\n'
        '        elif any(w.startswith(f"  {fn}:") for w in warnings):\n'
        '            status = "\u26a0\ufe0f"\n'
    )
    new = (
        "        if missing:\n"
        '            status = "\u274c"\n'
        '        elif any(w.startswith(f"  {fn}:") for w in warnings):\n'
        '            status = "\u26a0\ufe0f"\n'
        "        else:\n"
        '            status = "\u2713"\n'
    )
    if old not in t:
        print("[patch_data] validate_styles.py：锚点未命中（可能已修补）", file=sys.stderr)
        return
    with open(p, "w", encoding="utf-8") as f:
        f.write(t.replace(old, new))
    print("[patch_data] validate_styles.py 死条件已清理")


if __name__ == "__main__":
    # 注：phonk.json 的「轻冯/重冯」为有意的风格分类（冯=phonk），不做修改
    fix_validate_styles()