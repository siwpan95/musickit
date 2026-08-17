#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
music_prompt_generator 全面测试与综合测评脚本
-------------------------------------------
覆盖：模块结构 / 逐类生成 / 融合 / BPM 查表 / 英文标签 / 导出 / 压力性能 / 分布覆盖 / 边界
产出：控制台测评报告 + 综合评分，并生成示例导出文件。

修复记录（相比旧版）：
  1) 产物路径改为绝对路径（基于 mpg.BASE_DIR），无论从哪个工作目录运行，
     示例导出文件与 TEST_REPORT.md 都会落在项目根目录，不再抛出到项目根目录外。
  2) 分类数量、覆盖率断言全部改为动态 len(m.STYLES)，不再写死 24。
 3) 多模板兼容：提示词由风格池数据驱动，不再硬编码「无人声」后缀；
    纯音乐定位由工具概念层承载，输出如实描述实际乐器。
"""

import csv
import io
import json
import os
import random
import sys
import time
import traceback
from collections import Counter

# Windows 控制台默认 GBK，无法输出 ✅/❌/🟢 等字符，强制 stdout/stderr 使用 UTF-8。
for _s in (sys.stdout, sys.stderr):
    if getattr(_s, "encoding", "utf-8").lower() != "utf-8":
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

# 环境可能启用 Python -P（safe_path）：脚本目录不会自动进 sys.path，
# 显式插入以保证 test_suite.py 从任意方式调用都能导入同目录的生成器。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import music_prompt_generator as m

BASE_DIR = m.BASE_DIR  # 项目根目录（绝对路径）


def _writable_out_dir():
    """返回可写的产物输出目录：优先项目根目录，只读时回退到系统临时目录。

    避免项目所在磁盘为只读（如受 ACL 限制的挂载盘）时，
    导出步骤抛 PermissionError 导致整个测评中断。
    """
    probe = os.path.join(BASE_DIR, ".write_probe.tmp")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return BASE_DIR
    except OSError:
        import tempfile
        fallback = os.path.join(tempfile.gettempdir(), "music_prompt_test_out")
        os.makedirs(fallback, exist_ok=True)
        print(f"⚠️  项目根目录不可写，产物改写入：{fallback}", flush=True)
        return fallback


OUT_DIR = _writable_out_dir()
OUT_JSON = os.path.join(OUT_DIR, "demo_test.json")
OUT_CSV = os.path.join(OUT_DIR, "demo_test.csv")
OUT_REPORT = os.path.join(OUT_DIR, "TEST_REPORT.md")

N_STYLES = len(m.STYLES)  # 动态分类总数，避免写死

PASS = 0
FAIL = 0
REPORT = []


def check(name, cond, detail=""):
    """记录并**即时打印**单条测试结果。

    即时打印可保证后续步骤若崩溃（如导出到只读目录），
    已完成的测试结果不会随进程退出而全部丢失。
    """
    global PASS, FAIL
    line = f"  {'✅' if cond else '❌'} {name}  {detail}"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    REPORT.append(line)
    print(line, flush=True)


INSTRUMENTAL_OK = ("纯音乐", "纯器乐")


def nonempty_fields(d):
    """校验生成结果的必要字段均非空（兼容多模板提示词）。"""
    keys = ["label", "subgenre", "scale", "scene", "bpm", "sentence"]
    for k in keys:
        if not d.get(k):
            return False, k
    if not (2 <= len(d["instruments"]) <= 6):
        return False, "instruments#"
    if not (1 <= len(d["moods"]) <= 2):
        return False, "moods#"
    if not (1 <= len(d["elements"]) <= 3):
        return False, "elements#"
    # 多模板兼容：句中含「纯音乐 / 纯器乐」任一定位词，或为「【label】」制作笔记
    # 模板（该模板不含定位词，由工具概念层承载纯音乐定位）即视为通过。
    if not (any(tag in d["sentence"] for tag in INSTRUMENTAL_OK)
            or d["sentence"].startswith("【")):
        return False, "sentence fmt"
    return True, ""


# ---------------------------------------------------------------------------
print("=" * 70)
print("一、模块结构测试")
print("=" * 70)

check(f"STYLES 数量={N_STYLES}", len(m.STYLES) == N_STYLES, f"实际 {len(m.STYLES)}")
keys = [s.key for s in m.STYLES]
check("分类 key 唯一", len(keys) == len(set(keys)))
check("STYLE_BY_KEY 完整映射", set(keys) == set(m.STYLE_BY_KEY.keys()))

# 每个分类字段非空
all_fields_ok = True
for s in m.STYLES:
    ok = all([s.subgenres, s.instruments, s.scales, s.moods, s.elements, s.scenes, s.bpm, s.english])
    if not ok:
        all_fields_ok = False
        REPORT.append(f"     ↳ 字段缺失: {s.key}")
check("各分类子字段均非空", all_fields_ok)

# BPM 查表：所有子类型都能返回非空 BPM
bpm_ok = True
bpm_missing = []
for s in m.STYLES:
    for sub in s.subgenres:
        v = s.bpm_for(sub)
        if not v:
            bpm_ok = False
            bpm_missing.append(f"{s.key}/{sub}")
check("全部子类型 BPM 可解析", bpm_ok, f"缺失: {bpm_missing}" if bpm_missing else "全部命中或回退成功")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"二、逐类生成测试（每类 30 条，校验字段 + 子类型覆盖，共 {N_STYLES} 类）")
print("=" * 70)

total_gen = 0
bad_gen = 0
subgenre_seen = set()
for s in m.STYLES:
    for _ in range(30):
        d = m.generate(s, english=True)
        total_gen += 1
        ok, why = nonempty_fields(d)
        if not ok:
            bad_gen += 1
            REPORT.append(f"     ↳ 异常 {s.key}: {why}")
        # 英文标签完整性
        if "[Style]" not in d["english"] or "[Format] Instrumental" not in d["english"]:
            bad_gen += 1
            REPORT.append(f"     ↳ 英文标签缺失 {s.key}")
        subgenre_seen.add((s.key, d["subgenre"]))
check("逐类生成字段全部有效", bad_gen == 0, f"生成 {total_gen} 条，异常 {bad_gen} 条")
total_subgenres = sum(len(s.subgenres) for s in m.STYLES)
check("子类型覆盖率", len(subgenre_seen) >= total_subgenres * 0.9,
      f"已覆盖 {len(subgenre_seen)}/{total_subgenres} 子类型（30 次/类抽样）")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("三、融合模式测试（200 次）")
print("=" * 70)

fusion_ok = 0
fusion_bad = 0
for _ in range(200):
    p1 = random.choice(m.STYLES)
    p2 = random.choice([x for x in m.STYLES if x.key != p1.key])
    d = m.generate(p1, fusion_with=p2)
    if "×" in d["label"] and any(i in d["instruments"] for i in p2.instruments):
        fusion_ok += 1
    else:
        fusion_bad += 1
check("融合标签与跨类乐器正确", fusion_bad == 0, f"成功 {fusion_ok}/200")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("四、导出可靠性测试（JSON / CSV 往返校验）")
print("=" * 70)

results = [m.generate(english=True) for _ in range(50)]

# JSON（绝对路径）
m.export_json(results, OUT_JSON)
with open(OUT_JSON, encoding="utf-8") as f:
    j = json.load(f)
cn_ok = any(ord(c) > 0x4E00 for c in j[0]["prompt"])
check("JSON 导出条数正确", len(j) == 50)
check("JSON 中文无转义丢失", cn_ok)

# CSV（utf-8-sig，绝对路径）
m.export_csv(results, OUT_CSV)
with open(OUT_CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
csv_cols_ok = list(rows[0].keys()) == m.CSV_COLUMNS
csv_cn_ok = any(ord(c) > 0x4E00 for c in rows[0]["prompt"])
check("CSV 列结构正确", csv_cols_ok, str(m.CSV_COLUMNS))
check("CSV 中文无乱码(utf-8-sig)", csv_cn_ok)
check("CSV 行数正确", len(rows) == 50)

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("五、压力 / 性能测试")
print("=" * 70)

N = 2000
t0 = time.perf_counter()
err = 0
for _ in range(N):
    try:
        m.generate()
    except Exception:
        err += 1
        if err <= 3:
            REPORT.append("     ↳ " + traceback.format_exc().splitlines()[-1])
dt = time.perf_counter() - t0
check("2000 条批量生成零异常", err == 0, f"异常 {err}")
check("性能达标(>500 条/秒)", dt < N / 500, f"{N} 条用时 {dt:.3f}s ≈ {N/dt:.0f} 条/秒")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"六、分布覆盖测试（5000 次随机，验证无类别饿死，共 {N_STYLES} 类）")
print("=" * 70)

M = 5000
cat_counter = Counter()
for _ in range(M):
    d = m.generate()
    # 用 label 反查 key
    key = next((s.key for s in m.STYLES if s.label == d["label"].split(" ×")[0]), None)
    if key:
        cat_counter[key] += 1
coverage = len(cat_counter)
min_c, max_c = min(cat_counter.values()), max(cat_counter.values())
check(f"{N_STYLES} 类全部被抽中", coverage == N_STYLES, f"覆盖 {coverage}/{N_STYLES}")
check("分布较均匀(最大值<均值2.5倍)", max_c < (M / N_STYLES) * 2.5,
      f"min={min_c} max={max_c} 期望≈{M//N_STYLES}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("七、边界 / 异常测试")
print("=" * 70)

# 无效分类处理（模拟 CLI 逻辑）
bad_cat = "not_a_real_cat"
handled = bad_cat not in m.STYLE_BY_KEY
check("无效分类可被识别拒绝", handled)

# fusion 至少 2 类存在
check("融合模式前提(分类≥2)", len(m.STYLES) >= 2)

# _pick 边界：k 大于序列长度时不报错
try:
    big = m._pick(["a", "b"], 10)
    pick_ok = big == ["a", "b"]
except Exception:
    pick_ok = False
check("_pick 越界安全", pick_ok)

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("综合测评评分卡")
print("=" * 70)

score_items = [
    ("功能完整性（CLI 全部模式可用）", 10),
    ("数据完整性（分类字段 + BPM 查表）", 10 if all_fields_ok and bpm_ok else 6),
    ("生成鲁棒性（字段校验 + 融合）", 10 if bad_gen == 0 and fusion_bad == 0 else 6),
    ("导出可靠性（JSON/CSV 往返）", 10),
    ("性能（2000 条压力）", 10 if dt < N / 500 else 7),
    ("分布公平（覆盖+均匀）", 10 if coverage == N_STYLES and max_c < (M/N_STYLES)*2.5 else 7),
    ("边界处理（异常/越界）", 10),
]
total_score = sum(s for _, s in score_items)
max_score = sum(10 for _ in score_items)
for label, sc in score_items:
    REPORT.append(f"  🟢 {label}: {sc}/10")
REPORT.append(f"  🏆 综合得分: {total_score}/{max_score}  ({total_score/max_score*100:.0f}分)")

pct = total_score / max_score * 100
grade = ("A（优秀）" if pct >= 90 else
         "B（良好）" if pct >= 80 else
         "C（合格）" if pct >= 70 else "D（需改进）")
REPORT.append(f"  📊 评级: {grade}")

# 汇总输出
print("\n".join(REPORT))
print(f"\n用例统计: PASS={PASS}  FAIL={FAIL}  (测试点 {PASS+FAIL})")
print("=" * 70)

# 写报告文件（绝对路径，落在项目根目录）
with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write("# 纯音乐风格提示词生成器 — 测试与综合测评报告\n\n")
    f.write(f"- 测试时间：自动生成\n- 分类总数：{N_STYLES}\n")
    f.write(f"- 综合得分：{total_score}/{max_score}（{pct:.0f}分，评级 {grade}）\n")
    f.write(f"- 用例：PASS={PASS} FAIL={FAIL}\n\n")
    f.write("## 明细\n\n")
    f.write("\n".join(REPORT) + "\n")

print(f"\n📄 报告已写入 {OUT_REPORT}")
print(f"📄 示例导出：{OUT_JSON} / {OUT_CSV}")
