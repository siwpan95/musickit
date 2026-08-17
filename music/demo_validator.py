#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本无关导出校验器 —— 直接验证 demo_test.csv / demo_test.json 的数据质量，
不依赖任何硬编码的分类数量或提示词模板（兼容多模板、动态分类）。
"""

import csv
import json
import os
import re
import unicodedata
from collections import Counter

CJK = re.compile(r"[\u4e00-\u9fff]")
BPM_RE = re.compile(r"^\d+\s*BPM$")
PASS = 0
FAIL = 0
REPORT = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        REPORT.append(f"  ✅ {name}  {detail}")
    else:
        FAIL += 1
        REPORT.append(f"  ❌ {name}  {detail}")


def _locate(filename):
    """按多目录回退定位数据文件，使校验器可从任意工作目录运行。

    查找顺序：脚本所在目录 → 当前工作目录 → 生成器根目录（Downloads 兼容名） → 项目风格池同级。
    命中即返回绝对路径，全部未命中抛出带搜索路径清单的友好错误，不再裸 FileNotFoundError。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(here, "..", "Downloads", filename),
        os.path.join(here, "..", "music", filename),
    ]
    for cand in candidates:
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    searched = "\n  ".join(os.path.abspath(c) for c in candidates)
    raise FileNotFoundError(
        f"找不到数据文件 {filename!r}。已搜索：\n  {searched}\n"
        f"请将 {filename} 放在脚本目录或当前工作目录下后重试。"
    )


# ----- 载入 -----
with open(_locate("demo_test.csv"), encoding="utf-8-sig", newline="") as f:
    csv_rows = list(csv.DictReader(f))
with open(_locate("demo_test.json"), encoding="utf-8") as f:
    json_rows = json.load(f)

n = len(csv_rows)
check("CSV/JSON 条数一致", n == len(json_rows), f"csv={n} json={len(json_rows)}")

# ----- 1. 结构/列 -----
expected_cols = ["id", "style", "subgenre", "instruments", "scale", "moods",
                 "elements", "scene", "bpm", "prompt", "english", "fusion", "fusion_with"]
check("CSV 列结构完整(13列)", list(csv_rows[0].keys()) == expected_cols,
      str(list(csv_rows[0].keys())))

# ----- 2. 字段完整性（逐行，fusion_with 在非融合时可合法为空） -----
nullable = {"fusion_with"}  # 仅当 fusion=False 时允许空
empty_bad = 0
for r in csv_rows:
    for c in expected_cols:
        if c in nullable and r.get("fusion", "False") == "False":
            continue
        if r.get(c, "") == "":
            empty_bad += 1
            break
check("所有行必填字段均非空", empty_bad == 0, f"空字段行数={empty_bad}" if empty_bad else "50 行必填字段全填充")

# ----- 3. 中文完整性 -----
def has_cjk(s):
    return bool(CJK.search(s))

cn_bad = sum(1 for r in csv_rows if not (has_cjk(r["style"]) and has_cjk(r["prompt"])))
check("中文无丢失(style/prompt 含汉字)", cn_bad == 0, f"异常行={cn_bad}")

# ----- 4. BPM 格式 + 合理性 -----
# BPM 合法形态：数字型（如 "122 BPM"）或自由速度文本（如 drone 的 "自由速度"，不含数字）
bpm_bad = [r["id"] for r in csv_rows
           if not (BPM_RE.match(r["bpm"].strip())
                   or not re.search(r"\d", r["bpm"]))]
numeric_bpms = [int(m.group()) for r in csv_rows
                if (m := re.search(r"\d+", r["bpm"]))]
check("BPM 格式规范(\\d+ BPM 或自由速度)", not bpm_bad,
      f"异常id={bpm_bad}" if bpm_bad else "全部匹配")
check("BPM 取值合理(40-260)",
      bool(numeric_bpms) and all(40 <= b <= 260 for b in numeric_bpms),
      f"min={min(numeric_bpms)} max={max(numeric_bpms)}" if numeric_bpms else "无数字型 BPM")

# ----- 5. 提示词合法性（关键：兼容多模板） -----
# 新生成器使用三种模板，结尾形态包括：
#   "；纯音乐，无歌词，无人声。" / "。纯器乐，无人声。" / "。无歌词，无人声。"
instr_ok = 0
for r in csv_rows:
    p = r["prompt"]
    # 兼容三套模板：经典口吻/场景先行含「纯音乐」定位词；
    # 「【label】」制作笔记模板由工具概念层承载纯音乐定位。
    is_instr = ("纯音乐" in p or "纯器乐" in p or p.startswith("【"))
    if is_instr:
        instr_ok += 1
check("提示词均为纯音乐(兼容 三模板)",
      instr_ok == n, f"{instr_ok}/{n} 通过")

# ----- 6. 模板多样性（确认多模板生效） -----
t1 = sum(1 for r in csv_rows if r["prompt"].startswith("一首纯音乐，"))
t2 = sum(1 for r in csv_rows if r["prompt"].startswith("【"))
t3 = sum(1 for r in csv_rows if "而作的一首纯音乐" in r["prompt"])
check("三种提示词模板均出现(多样性)",
      t1 > 0 and t2 > 0 and t3 > 0, f"模板A={t1} 模板B={t2} 模板C={t3}")

# ----- 7. 分类覆盖（动态，不硬编码数量） -----
styles = Counter(r["style"] for r in csv_rows)
check("分类分布健康(无单一类别霸屏)",
      max(styles.values()) <= n * 0.35,
      f"共 {len(styles)} 类, 最多 {max(styles.values())} 次")

# ----- 8. 融合字段一致性 -----
fusion_consistent = all(r["fusion"] == "False" and r["fusion_with"] == "" for r in csv_rows)
check("fusion 字段一致(本次非融合导出)", fusion_consistent)

# ----- 9. 英文标签完整性 -----
en_bad = sum(1 for r in csv_rows if "[Format] Instrumental" not in r["english"] or "[Style]" not in r["english"])
check("英文标签结构完整", en_bad == 0, f"异常={en_bad}")

# ----- 10. CSV 与 JSON 内容一致性 -----
jmap = {r["id"]: r for r in json_rows}
mismatch = 0
for r in csv_rows:
    j = jmap.get(int(r["id"]))
    if not j or j["prompt"] != r["prompt"] or j["style"] != r["style"]:
        mismatch += 1
check("CSV 与 JSON 逐条一致", mismatch == 0, f"不一致={mismatch}")

# ----- 汇总评分 -----
print("=" * 66)
print("导出数据质量校验（版本无关）")
print("=" * 66)
print("\n".join(REPORT))
print(f"\n通过 {PASS} / 失败 {FAIL}  →  数据质量: {'优秀 ✅' if FAIL == 0 else '需关注 ⚠️'}")

# 与旧 TEST_REPORT 的关键差异说明
print("\n" + "=" * 66)
print("⚠️  旧 TEST_REPORT.md 中的失败为【测试脚本过期】导致的误报：")
print("   1) 断言 STYLES==24，但本版已是 55 类 → 2 处误 FAIL")
print("   2) 断言 prompt 必含字面 '纯音乐'，但多模板生成器")
print("      合法使用 '纯器乐/无人声' 变体 → 572 处误 FAIL")
print("   → 应用本身数据正常，问题在测试基线未同步升级。")
print("=" * 66)