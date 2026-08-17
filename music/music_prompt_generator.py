#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯音乐风格提示词随机生成器
========================
风格数据已从代码中抽离为 styles/ 目录下的多个 JSON 风格池文件
（每个文件对应一种流派），本文件仅保留「加载数据 + 运行逻辑」。

用法：
  python music_prompt_generator.py                 # 随机生成 1 条（全类）
  python music_prompt_generator.py -n 5           # 批量生成 5 条
  python music_prompt_generator.py -c phonk       # 指定分类生成
  python music_prompt_generator.py -c guofeng -e  # 附带英文标签
  python music_prompt_generator.py --fusion       # 跨类融合（如 国风+Phonk）
  python music_prompt_generator.py --list         # 列出所有分类
  python music_prompt_generator.py -n 20 --export json -o out.json   # 导出 JSON
  python music_prompt_generator.py -n 20 --export csv  -o out.csv    # 导出 CSV
  python music_prompt_generator.py -n 20 --export txt               # 导出 TXT（默认到脚本根目录）

扩展方式：在 styles/ 目录下新增一个 JSON（字段见已有文件）即可被自动加载。
"""

import argparse
import csv
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# 尽早将标准输出/错误重定向为 UTF-8（含 import 期的告警打印），
# 避免 Windows GBK 控制台下输出中文/emoji 时 UnicodeEncodeError。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 脚本所在根目录（生成文件默认输出到该绝对路径下）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 风格池目录：与本脚本同级的 styles/ 文件夹
STYLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles")


# ----------------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------------

@dataclass
class Subgenre:
    name: str
    bpm: str = ""


@dataclass
class StyleProfile:
    key: str
    label: str
    subgenres: List[Subgenre] = field(default_factory=list)
    instruments: List[str] = field(default_factory=list)
    scales: List[str] = field(default_factory=list)
    moods: List[str] = field(default_factory=list)
    elements: List[str] = field(default_factory=list)
    scenes: List[str] = field(default_factory=list)
    bpm: str = ""
    english: str = ""

    def bpm_for(self, sub: Subgenre) -> str:
        return sub.bpm or self.bpm

    @property
    def subgenre_names(self) -> List[str]:
        return [s.name for s in self.subgenres]

    def bpm_resolved(self, sub: Subgenre) -> str:
        """将 BPM 区间解析为具体整数（如 '110-130 BPM' → '122 BPM'）。"""
        raw = (sub.bpm or self.bpm or "").strip()
        if not raw:
            return ""
        # 提取所有数字（支持 '110-130' 区间 或 '118' 单值）
        nums = [int(x) for x in __import__("re").findall(r"\d+", raw)]
        if not nums:
            return raw
        if len(nums) >= 2:
            lo, hi = nums[0], nums[1]
            if lo > hi:
                lo, hi = hi, lo
            val = random.randint(lo, hi)
        else:
            val = nums[0]
        return f"{val} BPM"


# ----------------------------------------------------------------------------
# 风格池加载（从 JSON 文件）
# ----------------------------------------------------------------------------

# 风格文件必须包含的字段（缺任一则视为不完整，仍加载但告警）
REQUIRED_FIELDS = ["key", "label", "bpm", "subgenres",
                   "instruments", "scales", "moods", "elements", "scenes"]
OPTIONAL_FIELDS = ["english"]


def load_styles(directory: str = STYLES_DIR) -> List[StyleProfile]:
    """扫描目录下的所有 *.json，加载为风格集合。

    返回 (profiles, report)：profiles 为有效风格列表，report 为加载统计。
    """
    profiles: List[StyleProfile] = []
    report = {"total": 0, "loaded": 0, "skipped": 0, "incomplete": 0,
              "warnings": []}

    if not os.path.isdir(directory):
        report["warnings"].append(f"未找到风格池目录：{directory}")
        print(f"❌ 未找到风格池目录：{directory}")
        return profiles

    for fn in sorted(os.listdir(directory)):
        if not fn.lower().endswith(".json"):
            continue
        report["total"] += 1
        path = os.path.join(directory, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            report["skipped"] += 1
            msg = f"跳过无法解析的风格文件 {fn}：{e}"
            report["warnings"].append(msg)
            print(f"⚠️  {msg}")
            continue

        # 顶层必须是对象（dict），否则无法作为风格加载
        # （防止数组根/标量导致后续 data.get 抛 AttributeError，对齐 validate_styles.py）
        if not isinstance(data, dict):
            report["skipped"] += 1
            msg = f"风格文件 {fn} 顶层不是 JSON 对象（疑似数组/标量），已跳过"
            report["warnings"].append(msg)
            print(f"⚠️  {msg}")
            continue

        # 字段完整性校验
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            report["incomplete"] += 1
            msg = f"风格文件 {fn} 缺少字段：{', '.join(missing)}（仍加载）"
            report["warnings"].append(msg)
            print(f"⚠️  {msg}")

        subs = [Subgenre(name=s.get("name", ""), bpm=s.get("bpm", ""))
                for s in data.get("subgenres", [])]
        profiles.append(StyleProfile(
            key=data.get("key", fn[:-5]),
            label=data.get("label", fn[:-5]),
            english=data.get("english", ""),
            subgenres=subs,
            instruments=data.get("instruments", []),
            scales=data.get("scales", []),
            moods=data.get("moods", []),
            elements=data.get("elements", []),
            scenes=data.get("scenes", []),
            bpm=data.get("bpm", ""),
        ))
        report["loaded"] += 1
    return profiles, report


# 在导入时即加载（供 --category 自动补全提示等使用）
_raw = load_styles()
STYLES, _LOAD_REPORT = _raw if isinstance(_raw, tuple) else (
    _raw, {"total": 0, "loaded": 0, "skipped": 0,
           "incomplete": 0, "warnings": []})
STYLE_BY_KEY = {s.key: s for s in STYLES}


# ----------------------------------------------------------------------------
# 生成层
# ----------------------------------------------------------------------------

def _pick(seq, k):
    """从序列中随机取 k 个（不足则全取）。"""
    if k >= len(seq):
        return list(seq)
    return random.sample(seq, k)


def generate(profile: Optional[StyleProfile] = None,
             fusion_with: Optional[StyleProfile] = None,
             english: bool = False) -> dict:
    """生成单条提示词数据字典。"""
    if profile is None:
        profile = random.choice(STYLES)

    is_fusion = bool(fusion_with and fusion_with.key != profile.key)

    sub = random.choice(profile.subgenres) if profile.subgenres else Subgenre("")
    n_inst = random.randint(2, 4)
    insts = list(_pick(profile.instruments, n_inst))  # list 便于融合后去重
    scale = random.choice(profile.scales) if profile.scales else ""
    moods = list(_pick(profile.moods, random.randint(1, 2)))
    elements = list(_pick(profile.elements, random.randint(1, 2)))
    scene = random.choice(profile.scenes) if profile.scenes else ""
    bpm = profile.bpm_resolved(sub)  # BPM 区间取整为具体数值

    # 融合模式：混入第二类乐器/元素/情绪/场景，并做去重
    if is_fusion:
        other_inst = _pick(fusion_with.instruments, random.randint(1, 2))
        other_elem = _pick(fusion_with.elements, 1)
        other_mood = _pick(fusion_with.moods, 1)
        insts = list(dict.fromkeys(insts + list(other_inst)))      # 去重保序
        elements = list(dict.fromkeys(elements + list(other_elem)))
        moods = list(dict.fromkeys(moods + list(other_mood)))
        # 50% 概率采用第二类的场景，让融合更有"跨类"味
        if fusion_with.scenes and random.random() < 0.5:
            scene = random.choice(fusion_with.scenes)
        fusion_label = f"{profile.label} × {fusion_with.label}"
        fusion_en = f"{profile.english} × {fusion_with.english}"
    else:
        fusion_label = profile.label
        fusion_en = profile.english

    sentence = _build_sentence(fusion_label, sub.name, insts, scale,
                               moods, bpm, elements, scene)
    en_tags = ""
    if english:
        en_tags = (
            f"[Style] {fusion_en} / {sub.name} | "
            f"[Instruments] {', '.join(insts)} | "
            f"[Scale] {scale} | "
            f"[Mood] {', '.join(moods)} | "
            f"[Tempo] {bpm} | "
            f"[Scene] {scene} | "
            f"[Format] Instrumental"
        )

    return {
        "label": fusion_label,
        "subgenre": sub.name,
        "instruments": insts,
        "scale": scale,
        "moods": moods,
        "elements": elements,
        "scene": scene,
        "bpm": bpm,
        "sentence": sentence,
        "english": en_tags,
        "fusion": is_fusion,
        "fusion_with": fusion_with.key if is_fusion else "",
    }


def _build_sentence(label, sub_name, insts, scale, moods, bpm, elements, scene):
    """按多套模板组装提示词，动态省略空字段，避免语病。

    注：模板不再硬编码「无人声 / 纯器乐」等结尾声明——乐器清单（insts）
    直接来自风格池，若风格池含人声类乐器则如实呈现，避免自相矛盾。
    「纯音乐」定位由工具/风格池概念层承载，而非写死在每一句提示词尾部。
    """
    parts = []
    # 模板 0：经典口吻
    t0 = (
        f"一首纯音乐，{label}风格"
        + (f"，{sub_name}取向" if sub_name else "")
        + (f"，以{'、'.join(insts)}为主奏" if insts else "")
        + (f"，采用{scale}" if scale else "")
        + (f"，情绪{'、'.join(moods)}" if moods else "")
        + (f"，速度{bpm}" if bpm else "")
        + (f"，融入{'、'.join(elements)}" if elements else "")
        + (f"，适合{scene}" if scene else "")
    )
    # 模板 1：更简练的"制作笔记"口吻
    t1 = (
        f"【{label}】"
        + (f" · {sub_name}" if sub_name else "")
        + (f" · 主奏：{'、'.join(insts)}" if insts else "")
        + (f" · 调式：{scale}" if scale else "")
        + (f" · 情绪：{'、'.join(moods)}" if moods else "")
        + (f" · {bpm}" if bpm else "")
        + (f" · 细节：{'、'.join(elements)}" if elements else "")
        + (f" · 场景：{scene}" if scene else "")
    )
    # 模板 2：场景先行
    t2 = (
        (f"为{scene}而作的一首纯音乐：" if scene else "一首纯音乐：")
        + f"{label}"
        + (f"（{sub_name}）" if sub_name else "")
        + (f"，以{'、'.join(insts)}编织" if insts else "")
        + (f"，{scale}调式" if scale else "")
        + (f"，{'、'.join(moods)}的情绪" if moods else "")
        + (f"，{bpm}" if bpm else "")
        + (f"，点缀{'、'.join(elements)}" if elements else "")
    )
    return random.choice([t0, t1, t2])


def batch_generate(n, profile=None, dedup=True, fusion=False,
                   english=False, seed=None) -> List[dict]:
    """批量生成 n 条提示词，供 CLI 与 GUI 共用（消除两边生成循环漂移）。

    - dedup=True 时按 sentence 指纹去重，保证每条差异（达到上限或凑不满则停止）
    - fusion=True 且风格池≥2 时每条随机混搭第二类；不足 2 个风格则自动退回非融合
    - seed 固定则结果可复现
    """
    if seed is not None:
        random.seed(seed)
    results: List[dict] = []
    seen = set()
    target = max(1, int(n))
    attempts = 0
    while len(results) < target and attempts < target * 20:
        attempts += 1
        if fusion and len(STYLES) >= 2:
            p1 = profile or random.choice(STYLES)
            others = [s for s in STYLES if s.key != p1.key]
            data = (generate(p1, fusion_with=random.choice(others), english=english)
                    if others else generate(p1, english=english))
        else:
            data = generate(profile, english=english)
        # 去重：仅当「关闭去重」或「该句未出现过」才收录
        if (not dedup) or (data["sentence"] not in seen):
            seen.add(data["sentence"])
            results.append(data)
    return results


def render(data: dict, english: bool) -> str:
    """将生成数据渲染为可读文本。"""
    lines = []
    lines.append(f"🎵 风格：{data['label']} ｜ 子类型：{data['subgenre']}")
    lines.append(f"   🎼 乐器：{'、'.join(data['instruments'])}")
    lines.append(f"   🎚  调式：{data['scale']}")
    lines.append(f"   💡 情绪：{'、'.join(data['moods'])}")
    lines.append(f"   ⏱  速度：{data['bpm']}")
    lines.append(f"   🎛  元素：{'、'.join(data['elements'])}")
    lines.append(f"   📍 场景：{data['scene']}")
    lines.append("")
    lines.append(f"   📝 提示词：{data['sentence']}")
    if english:
        lines.append(f"   🌐 EN   ：{data['english']}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# 导出层
# ----------------------------------------------------------------------------

CSV_COLUMNS = [
    "id", "style", "subgenre", "instruments", "scale",
    "moods", "elements", "scene", "bpm", "prompt", "english",
    "fusion", "fusion_with",
]


def _default_export_path(ext: str) -> str:
    """生成带时间戳且不与现有文件冲突的默认导出路径，避免覆盖旧导出。

    形如 music_prompts_20260815_205000.txt；同秒内冲突时追加 _1、_2 递增。
    CLI 与 GUI 共用此函数，保证默认命名逻辑单一来源。
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(BASE_DIR, f"music_prompts_{stamp}")
    path = f"{base}.{ext}"
    i = 1
    while os.path.exists(path):
        path = f"{base}_{i}.{ext}"
        i += 1
    return path


def _flatten(data: dict, idx: int) -> dict:
    """将生成结果扁平化为单层级字典（用于导出）。"""
    return {
        "id": idx,
        "style": data["label"],
        "subgenre": data["subgenre"],
        "instruments": "、".join(data["instruments"]),
        "scale": data["scale"],
        "moods": "、".join(data["moods"]),
        "elements": "、".join(data["elements"]),
        "scene": data["scene"],
        "bpm": data["bpm"],
        "prompt": data["sentence"],
        "english": data["english"],
        "fusion": data.get("fusion", False),
        "fusion_with": data.get("fusion_with", ""),
    }


def export_json(results: List[dict], path: str) -> None:
    flat = [_flatten(r, i + 1) for i, r in enumerate(results)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)


def export_csv(results: List[dict], path: str) -> None:
    # utf-8-sig 让 Excel 正确识别中文
    flat = [_flatten(r, i + 1) for i, r in enumerate(results)]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(flat)


def export_txt(results: List[dict], path: str) -> None:
    """将生成内容以可读的纯文本形式导出（UTF-8，绝对路径输出）。"""
    lines: List[str] = []
    lines.append("纯音乐风格提示词生成结果")
    lines.append("共 %d 条 · 生成时间（本地）：请于文件属性查看" % len(results))
    lines.append("=" * 64)
    for i, data in enumerate(results):
        if i > 0:
            lines.append("-" * 64)
        head = f"【#{i + 1}】"
        if data.get("fusion"):
            head += f"  融合:{data['fusion_with']}"
        lines.append(head)
        lines.append(f"风格：{data['label']}")
        if data["subgenre"]:
            lines.append(f"子流派：{data['subgenre']}")
        if data["instruments"]:
            lines.append(f"乐器：{'、'.join(data['instruments'])}")
        if data["scale"]:
            lines.append(f"调式：{data['scale']}")
        if data["moods"]:
            lines.append(f"情绪：{'、'.join(data['moods'])}")
        if data["elements"]:
            lines.append(f"细节：{'、'.join(data['elements'])}")
        if data["scene"]:
            lines.append(f"场景：{data['scene']}")
        if data["bpm"]:
            lines.append(f"速度：{data['bpm']}")
        lines.append(f"提示词：{data['sentence']}")
        if data.get("english"):
            lines.append(f"EN：{data['english']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# CLI 层
# ----------------------------------------------------------------------------

def main():
    # 允许通过参数覆盖风格池目录（覆盖已加载的全局）
    global STYLES, STYLE_BY_KEY, _LOAD_REPORT

    parser = argparse.ArgumentParser(
        description="纯音乐风格提示词随机生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-n", "--num", type=int, default=1, help="生成条数（默认 1）")
    parser.add_argument("-c", "--category", type=str, default=None,
                        help="指定分类 key：" + " / ".join(STYLE_BY_KEY.keys()))
    parser.add_argument("-e", "--english", action="store_true", help="附带英文标签")
    parser.add_argument("--fusion", action="store_true", help="跨类融合生成（随机混搭两类）")
    parser.add_argument("--list", action="store_true", help="列出所有分类及 key")
    parser.add_argument("--export", type=str, choices=["json", "csv", "txt"], default=None,
                        help="导出格式（json / csv / txt），与 -n 配合批量生成")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="导出文件路径（默认：脚本根目录下 music_prompts_<时间戳>.<格式>，不覆盖旧文件）")
    parser.add_argument("--styles-dir", type=str, default=STYLES_DIR,
                        help="自定义风格池目录（默认脚本同级 styles/）")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子（设置后可复现生成结果）")
    parser.add_argument("--no-dedup", action="store_true",
                        help="关闭批量生成的去重（默认开启，保证每条差异）")
    args = parser.parse_args()

    if args.styles_dir != STYLES_DIR:
        loaded = load_styles(args.styles_dir)
        STYLES, _LOAD_REPORT = (loaded if isinstance(loaded, tuple)
                                else (loaded, _LOAD_REPORT))
        STYLE_BY_KEY = {s.key: s for s in STYLES}

    if not STYLES:
        print("❌ 没有任何可用风格，请检查 styles/ 目录。")
        sys.exit(2)

    # 加载报告（字段完整性 / 跳过情况）
    if _LOAD_REPORT.get("warnings"):
        print(f"📋 风格池加载：共 {_LOAD_REPORT['total']} 个文件，"
              f"成功 {_LOAD_REPORT['loaded']}，跳过 {_LOAD_REPORT['skipped']}，"
              f"不完整 {_LOAD_REPORT['incomplete']}。")

    if args.list:
        print(f"共 {len(STYLES)} 个分类（key → 名称）：")
        for s in STYLES:
            meta = f"BPM {s.bpm}" if s.bpm else "（无 BPM）"
            print(f"  {s.key:<14} → {s.label}  ｜ {meta} ｜ 子流派 {len(s.subgenres)}")
        return

    profile = None
    if args.category:
        if args.category not in STYLE_BY_KEY:
            print(f"❌ 未知分类 '{args.category}'，可用：{', '.join(STYLE_BY_KEY.keys())}")
            sys.exit(2)
        profile = STYLE_BY_KEY[args.category]

    # 设置随机种子（可复现）
    if args.seed is not None:
        random.seed(args.seed)

    # 导出模式下，若未显式指定条数则默认 10 条
    if args.export and args.num == 1:
        args.num = 10

    # 条数必须为正整数
    if args.num < 1:
        print(f"❌ 生成条数必须为正整数，收到：{args.num}")
        sys.exit(2)

    # 批量生成（去重/融合/可复现逻辑统一由 batch_generate 处理，CLI 与 GUI 共用）
    results = batch_generate(
        args.num, profile,
        dedup=not args.no_dedup,
        fusion=args.fusion,
        english=args.english,
        seed=args.seed,
    )

    # 导出优先：写文件并简要反馈，不打印全部详情
    if args.export:
        ext = args.export
        # 默认文件名带时间戳（不覆盖旧导出）；显式 -o 时尊重用户指定路径
        path = args.output or _default_export_path(ext)
        path = os.path.abspath(path)
        try:
            if ext == "json":
                export_json(results, path)
            elif ext == "txt":
                export_txt(results, path)
            else:
                export_csv(results, path)
        except OSError as e:
            print(f"❌ 导出失败（无法写入 {path}）：{e}")
            sys.exit(1)
        print(f"✅ 已导出 {len(results)} 条提示词 → {path}"
              + (f"（种子 {args.seed}）" if args.seed is not None else ""))
        return

    print("=" * 64)
    for i, data in enumerate(results):
        if i > 0:
            print("-" * 64)
        print(f"【#{i + 1}】"
              + (f"  🔀融合:{data['fusion_with']}" if data["fusion"] else ""))
        print(render(data, args.english))
    print("=" * 64)


if __name__ == "__main__":
    # Windows 控制台默认使用 GBK 编码，无法输出中文与 emoji，
    # 强制将标准输出/错误重定向为 UTF-8，避免 UnicodeEncodeError。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    random.seed()  # 使用系统熵，保证每次运行不同
    main()
