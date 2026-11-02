#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_doc_counts —— 文档里写死的测试数字，必须与真实收集数一致。

为什么需要：README 里「**N passed**」「N 个纯逻辑用例」这类数字是手写的，
每加一条用例就静默过期一次。这个仓库已经因为「文档说 X、实际 Y」踩过好几次
（`--release-safe` 守红线、`7 处写死 ✅ 修复`、125 passed 早已是 191），
所以把这件事做成 <5 秒能跑的机械检查，而不是靠人记得改。

检查对象：
  README.md        全量 passed / 引擎侧 / 桥接器侧 / 冒烟纯逻辑用例数
  music/README.md  桥接器用例数、纯逻辑档用例数

退出码：0 一致 / 1 不一致 / 2 环境问题（pytest 跑不起来）

用法：
  python scripts/check_doc_counts.py            # 检查
  python scripts/check_doc_counts.py --fix      # 把数字改对（仅这两类数字）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ("remix/tests", "music/tests")


def _count(targets: list[str], extra: list[str] | None = None) -> int:
    """用 --collect-only 数用例（不执行，快且无副作用）。"""
    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--collect-only",
           *(extra or [])]
    env = dict(os.environ)
    # 本机装了会炸的 pytest 插件（hydra → antlr4 → typing.io），收集阶段就 ImportError
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    m = re.findall(r"^(\d+)/\d+ tests collected|^(\d+) tests? collected", out, re.M)
    if not m:
        print(out.strip()[-800:], file=sys.stderr)
        raise SystemExit(2)
    return int(m[-1][0] or m[-1][1])


def _manifest_total() -> int:
    """13 个池的 manifest 条目总数。

    为什么也纳入门禁：文档里会写「manifest 记着 N 条素材」，而每灌一次库这个数
    就变（本次加 137 条 iowa 采样就变了）。它是典型的"文档说 X 实际 Y"来源。
    """
    total = 0
    for pool in sorted(os.listdir(ROOT)):
        mp = os.path.join(ROOT, pool, "manifest.json")
        if not os.path.isfile(mp):
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        entries = data.get("entries") if isinstance(data, dict) else None
        if isinstance(entries, list):
            total += len(entries)
    return total


def _iowa_total() -> int:
    """爱荷华 MIS 素材的 manifest 条目数（文件名以 iowa__ 开头）。

    与 _manifest_total 一样是**入库索引**里的确定值：manifest 入库、音频不入库，
    所以干净克隆上也是这个数 —— 文档里写"灌了多少条"不会因机器而异。
    """
    n = 0
    for pool in sorted(os.listdir(ROOT)):
        mp = os.path.join(ROOT, pool, "manifest.json")
        if not os.path.isfile(mp):
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            continue
        n += sum(1 for e in entries
                 if isinstance(e, dict) and str(e.get("file", "")).startswith("iowa__"))
    return n


def actual() -> dict[str, int]:
    return {
        "total": _count(list(DIRS)),
        "remix": _count(["remix/tests"]),
        "music": _count(["music/tests"]),
        "smoke": _count(list(DIRS), ["-m", "smoke"]),
        "smoke_music": _count(["music/tests"], ["-m", "smoke"]),
        "manifest_total": _manifest_total(),
        "iowa_total": _iowa_total(),
    }


# (文件, 正则, 取值键, 人类可读名)
CHECKS = [
    # 注意用「用例」而不是「passed」：门禁数的是 --collect-only 的**收集数**，
    # 而 passed 数在有 skip 时会少一条（本仓 Tk 用例偶发 skip），两个口径不同名才对得上。
    ("README.md", r"\*\*(\d+) 用例\*\*", "total", "全量用例数"),
    ("README.md", r"引擎侧 (\d+)", "remix", "引擎侧用例数"),
    ("README.md", r"桥接器侧 (\d+)", "music", "桥接器侧用例数"),
    ("README.md", r"\*\*(\d+) 个纯逻辑用例\*\*", "smoke", "冒烟纯逻辑用例数"),
    ("music/README.md", r"单元测试（(\d+) 用例", "music", "桥接器用例数"),
    ("music/README.md", r"纯逻辑档（(\d+) 用例", "smoke_music", "桥接器纯逻辑档用例数"),
    # ONBOARDING.md（另一个会话新增的上手指南）：同样有手写数字，同样会过期。
    # 它原本不在门禁覆盖范围内，加了 137 条用例后数字就悄悄错了 —— 这正是门禁的意义。
    ("ONBOARDING.md", r"全量（(\d+) 条）", "total", "全量用例数（速查表）"),
    ("ONBOARDING.md", r"\*\*(\d+) 用例\*\*", "total", "全量用例数（正文）"),
    ("ONBOARDING.md", r"(?<![A-Za-z_])total=(\d+)", "total", "门禁输出里的 total"),
    ("ONBOARDING.md", r"(?<![A-Za-z_])remix=(\d+)", "remix", "门禁输出里的 remix"),
    ("ONBOARDING.md", r"(?<![A-Za-z_])music=(\d+)", "music", "门禁输出里的 music"),
    ("ONBOARDING.md", r"(?<![A-Za-z_])smoke=(\d+)", "smoke", "门禁输出里的 smoke"),
    ("ONBOARDING.md", r"(?<![A-Za-z_])smoke_music=(\d+)", "smoke_music", "门禁输出里的 smoke_music"),
    ("ONBOARDING.md", r"(\d+) passed(?:, \d+ skipped)?, \d+ deselected", "smoke", "冒烟档用例数"),
    ("ONBOARDING.md", r"登记了 (\d+) 条素材", "manifest_total", "manifest 条目总数"),
    ("ONBOARDING.md", r"manifest 记着 (\d+) 条", "manifest_total", "manifest 条目总数（doctor 段）"),
    ("ONBOARDING.md", r"合计\s+(\d+)", "manifest_total", "doctor 示例里的合计行"),
    ("ONBOARDING.md", r"灌入 (\d+) 条", "iowa_total", "爱荷华 MIS 素材条数"),
]


def _read(path: str) -> str:
    """按字节读再解码：保留原行尾（README 是 CRLF，用文本模式 + newline 写回会整篇改行尾）。"""
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def _write(path: str, text: str) -> None:
    """按字节写回，绝不改行尾 —— 否则 --fix 会产出一份 240 行全变的 diff。"""
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="校验文档中的测试数字与真实收集数一致")
    ap.add_argument("--fix", action="store_true", help="自动把文档数字改对")
    args = ap.parse_args()

    act = actual()

    print("真实收集数：" + "  ".join(f"{k}={v}" for k, v in act.items()))
    print()

    bad = 0
    # 每个文件只读一次，所有修复都累积在这份内存副本上（逐条重读会把前一处修复冲掉）
    texts: dict[str, str] = {}
    dirty: set[str] = set()
    for fname, pattern, key, label in CHECKS:
        if fname not in texts:
            texts[fname] = _read(os.path.join(ROOT, fname))
        found = re.findall(pattern, texts[fname])
        if not found:
            print(f"❌ {fname}: 找不到「{label}」的数字（正则 {pattern}）—— 文档措辞变了，门禁需同步")
            bad += 1
            continue
        for got in found:
            if int(got) == act[key]:
                print(f"✅ {fname}: {label} = {got}")
            else:
                print(f"❌ {fname}: {label} 文档写 {got}，实际 {act[key]}")
                bad += 1
                if args.fix:
                    texts[fname] = re.sub(
                        pattern,
                        lambda m2, _k=key: m2.group(0).replace(m2.group(1), str(act[_k])),
                        texts[fname])
                    dirty.add(fname)

    if args.fix and dirty:
        for fname in dirty:
            _write(os.path.join(ROOT, fname), texts[fname])
            print(f"✏️  已改写 {fname}")
        print("\n改完请重跑本脚本确认，并把改动一起提交。")
        return 0

    print()
    if bad:
        print(f"❌ {bad} 处不一致。改文档，或 python scripts/check_doc_counts.py --fix")
        return 1
    print("✅ 文档数字与真实一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
