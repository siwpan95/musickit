#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 musickit 规范乐器分类体系（instrument_taxonomy.json）。

数据来源：G:\\music\\musickit\\music\\styles\\*.json（63 个风格池，242 个不同乐器词）。
目标：把这 242 个“自由文本”乐器词归并为一套规范类目（canonical_class），
每类精确映射到 musickit 现有池（bass/drum/guita/cowbell/synth/acapella/animal/sfx）
+ 子类别 + 是否有样本（available）。

设计原则（消除“混用”）：
  - 不同乐器家族不再被压进 7 个粗池：钢琴/弦乐/铜管/笛箫/民族乐器等 musickit 无样本的，
    标记为 available=false，桥接器会跳过并报告缺口，而非假映射到错误池。
  - 真人声（人声/人声切片/Auto-Tune/合唱…）→ acapella 池，以 musickit 混音引擎的
    “vocal” 角色接入（structures.json 已有 vocal 层）。
  - 动物叫声池（animal）不再冒充人声；它只在随机混音里当 one-shot 替代层。

输出：G:\\music\\musickit\\instrument_taxonomy.json
用法：python build_instrument_taxonomy.py
"""

import glob
import json
import os
from collections import Counter, OrderedDict
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

MUSIC_STYLES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "music", "styles")
OUT = str(_MK_ROOT / "instrument_taxonomy.json")

# ---------------------------------------------------------------------------
# 规范类目元数据
#   pool        : 文件来源池（None 表示 musickit 无样本）
#   subcategory : 子类别（仅元数据，便于将来细选；当前桥接仍按池整池抽）
#   available   : 该池是否有真实样本可抽取
#   mixer_role  : 送入混音引擎的角色层键（structures.json），默认 = pool，
#                 真人声统一为 "vocal"
#   fallback    : available=false 时的建议回退池（桥接器默认不用，仅作提示）
#   note        : 说明
# ---------------------------------------------------------------------------
# 每类目优先抽取的子目录（与 instrument_taxonomy.json 的 prefer_subdirs 一致；
# 目录名与 G:\\music\\musickit\\<pool>\\ 下的真实目录核对）。桥接器按此字段先子目录、后整池。
PREFER_SUBDIRS = {
    "808_bass": ["808_bass"], "sub_bass": ["sub_bass"],
    "upright_bass": ["bass_guitar", "bass_misc"], "bass_guitar": ["bass_guitar", "bass_misc"],
    "hihat": ["hihat"], "drum_machine": ["drum_machine", "drums_acoustic"],
    "drums_acoustic": ["drums_acoustic", "drum_misc"], "percussion": ["percussion"],
    "guitar_slide": ["guitar_slide"], "guitar_distorted": ["guitar_distorted"],
    "guitar_rhythm": ["guitar_rhythm"], "guitar_acoustic": ["guitar_acoustic"],
    "guitar_electric": ["guitar_electric"], "guitar_misc": ["guitar", "guita_misc"],
    "cowbell": [],
    "synth_chip": ["synth_misc", "synth"], "synth_analog": ["synth_analog"],
    "synth_lead": ["synth_lead"], "synth_fm": ["synth_fm"],
    "synth_pad": ["synth_pad", "pad"], "synth_misc": ["synth_misc", "synth", "pad"],
    "vocal_tuned": ["vocal_tuned", "vocal_full"], "vocal_choir": ["vocal_choir", "vocal_full"],
    "vocal_chop": ["vocal_chop", "vocal_chops"], "vocal_full": ["vocal_full", "vocal"],
    "sfx_noise": ["sfx_noise"], "sfx_glitch": ["sfx_glitch"], "sfx_cinematic": ["sfx_cinematic"],
    "keys_piano": ["piano", "keys_piano", "keys"], "organ": ["organ"],
    "accordion": ["accordion"], "harp": ["harp"],
    "strings": ["strings", "bowed", "violin", "cello"],
    "brass": ["brass", "horn", "trumpet", "trombone"],
    "woodwind": ["woodwind", "recorder"],
    "ethnic_plucked": ["ethnic_plucked", "koto", "sitar"],
    "ethnic_bowed": ["ethnic_bowed", "ethnic"],
}

CLASSES = OrderedDict([
    # ---- BASS ----
    ("808_bass",     {"pool": "bass",    "subcategory": "808",     "available": True,  "mixer_role": "bass",    "fallback": None, "note": "808 贝斯"}),
    ("sub_bass",     {"pool": "bass",    "subcategory": "sub",     "available": True,  "mixer_role": "bass",    "fallback": None, "note": "重低音/下潜"}),
    ("upright_bass", {"pool": "bass",    "subcategory": "upright", "available": True,  "mixer_role": "bass",    "fallback": None, "note": "直立贝斯/低音提琴"}),
    ("bass_guitar",  {"pool": "bass",    "subcategory": "guitar",  "available": True,  "mixer_role": "bass",    "fallback": None, "note": "普通贝斯/贝斯线"}),

    # ---- DRUM ----
    ("hihat",          {"pool": "drum", "subcategory": "hihat",    "available": True, "mixer_role": "drum", "fallback": None, "note": "踩镲/碎拍镲"}),
    ("drum_machine",   {"pool": "drum", "subcategory": "machine",  "available": True, "mixer_role": "drum", "fallback": None, "note": "鼓机/四四拍鼓机"}),
    ("drums_acoustic", {"pool": "drum", "subcategory": "acoustic", "available": True, "mixer_role": "drum", "fallback": None, "note": "鼓组/底鼓/军鼓/爵士鼓"}),
    ("percussion",     {"pool": "drum", "subcategory": "perc",     "available": True, "mixer_role": "drum", "fallback": None, "note": "打击乐/沙锤/铃鼓/世界打击"}),

    # ---- GUITAR ----
    ("guitar_slide",     {"pool": "guita", "subcategory": "slide",    "available": True, "mixer_role": "guita", "fallback": None, "note": "滑音吉他"}),
    ("guitar_distorted", {"pool": "guita", "subcategory": "distorted", "available": True, "mixer_role": "guita", "fallback": None, "note": "失真/电吉他失真/雷鬼"}),
    ("guitar_rhythm",    {"pool": "guita", "subcategory": "rhythm",   "available": True, "mixer_role": "guita", "fallback": None, "note": "节奏吉他"}),
    ("guitar_acoustic",  {"pool": "guita", "subcategory": "acoustic", "available": True, "mixer_role": "guita", "fallback": None, "note": "原声/尼龙弦/钢吉他"}),
    ("guitar_electric",  {"pool": "guita", "subcategory": "electric", "available": True, "mixer_role": "guita", "fallback": None, "note": "电吉他长音"}),
    ("guitar_misc",      {"pool": "guita", "subcategory": "misc",     "available": True, "mixer_role": "guita", "fallback": None, "note": "其它吉他（兜底）"}),

    # ---- COWBELL ----
    ("cowbell", {"pool": "cowbell", "subcategory": "cowbell", "available": True, "mixer_role": "cowbell", "fallback": None, "note": "牛铃"}),

    # ---- SYNTH ----
    ("synth_chip",   {"pool": "synth", "subcategory": "chip",   "available": True, "mixer_role": "synth", "fallback": None, "note": "芯片音色"}),
    ("synth_analog", {"pool": "synth", "subcategory": "analog", "available": True, "mixer_role": "synth", "fallback": None, "note": "模拟/模块合成器/acid303"}),
    ("synth_lead",   {"pool": "synth", "subcategory": "lead",   "available": True, "mixer_role": "synth", "fallback": None, "note": "合成主音/明亮 lead"}),
    ("synth_fm",     {"pool": "synth", "subcategory": "fm",     "available": True, "mixer_role": "synth", "fallback": None, "note": "FM/波形/钟声"}),
    ("synth_pad",    {"pool": "synth", "subcategory": "pad",    "available": True, "mixer_role": "synth", "fallback": None, "note": "合成 pad/弦乐垫/混响墙"}),
    ("synth_misc",   {"pool": "synth", "subcategory": "misc",   "available": True, "mixer_role": "synth", "fallback": None, "note": "其它合成器"}),

    # ---- VOCAL（真人声 → acapella 池，以 vocal 角色接入）----
    ("vocal_tuned",  {"pool": "acapella", "subcategory": "tuned",  "available": True, "mixer_role": "vocal", "fallback": None, "note": "Auto-Tune 人声"}),
    ("vocal_choir",  {"pool": "acapella", "subcategory": "choir",  "available": True, "mixer_role": "vocal", "fallback": None, "note": "人声合唱/多部和声"}),
    ("vocal_chop",   {"pool": "acapella", "subcategory": "chop",   "available": True, "mixer_role": "vocal", "fallback": None, "note": "人声切片（用整曲人声代理）"}),
    ("vocal_full",   {"pool": "acapella", "subcategory": "full",   "available": True, "mixer_role": "vocal", "fallback": None, "note": "整曲真人声"}),

    # ---- SFX ----
    ("sfx_noise",     {"pool": "sfx", "subcategory": "noise",     "available": True, "mixer_role": "sfx", "fallback": None, "note": "黑胶/电路/比特失真噪点"}),
    ("sfx_glitch",    {"pool": "sfx", "subcategory": "glitch",    "available": True, "mixer_role": "sfx", "fallback": None, "note": "故障音"}),
    ("sfx_cinematic", {"pool": "sfx", "subcategory": "cinematic", "available": True, "mixer_role": "sfx", "fallback": None, "note": "激光/采样/电影/田野录音"}),

    # ---- 2026-08 起已补齐样本的家族（available=true，直接映射到新池）----
    ("keys_piano",   {"pool": "keys", "subcategory": "piano",    "available": True, "mixer_role": "keys", "fallback": "synth", "note": "钢琴/电钢/Rhodes（已补齐）"}),
    ("organ",        {"pool": "keys", "subcategory": "organ",    "available": True, "mixer_role": "keys", "fallback": "synth", "note": "风琴/管风琴（已补齐）"}),
    ("accordion",    {"pool": "keys", "subcategory": "accordion", "available": True, "mixer_role": "keys", "fallback": "synth", "note": "手风琴（已补齐）"}),
    ("harp",         {"pool": "keys", "subcategory": "harp",     "available": True, "mixer_role": "keys", "fallback": "synth", "note": "竖琴/水晶碗（已补齐）"}),
    ("strings",      {"pool": "strings", "subcategory": "strings",  "available": True, "mixer_role": "strings", "fallback": "synth", "note": "弦乐/小提琴/大提琴（已补齐）"}),
    ("brass",        {"pool": "brass", "subcategory": "brass",    "available": True, "mixer_role": "brass", "fallback": "synth", "note": "铜管/小号/长号/萨克斯（已补齐）"}),
    ("woodwind",     {"pool": "woodwind", "subcategory": "woodwind", "available": True, "mixer_role": "woodwind", "fallback": "synth", "note": "长笛/笛箫/笙/唢呐/木管（已补齐）"}),
    ("ethnic_plucked", {"pool": "ethnic", "subcategory": "ethnic_plucked", "available": True, "mixer_role": "ethnic", "fallback": "guita", "note": "三味线/琵琶/古筝/西塔琴等民族拨弦（已补齐）"}),
    ("ethnic_bowed", {"pool": "ethnic", "subcategory": "ethnic_bowed", "available": True, "mixer_role": "ethnic", "fallback": "guita", "note": "马头琴/奚琴等民族拉弦（已补齐）"}),
])

# ---------------------------------------------------------------------------
# 匹配规则：按优先级（具体在前，宽泛在后）。
# 每条 = (canonical_class, [keywords])
# 匹配：乐器词 lower 中包含任一 keyword（lower）即命中该类目。
# ---------------------------------------------------------------------------
RULES = [
    ("cowbell",        ["牛铃", "cowbell"]),
    ("808_bass",       ["808 贝斯", "808 bass", "808 滑音贝斯", "808"]),
    ("sub_bass",       ["重低音", "重贝斯", "wobble 贝斯", "bass drop", "重低音贝斯"]),
    ("upright_bass",   ["直立贝斯", "低音提琴"]),
    ("bass_guitar",    ["贝斯", "bass", "贝斯线", "贝斯线条", "模拟 bass", "合成贝斯", "slap 贝斯"]),

    ("hihat",          ["hi-hat", "闭镲", "碎拍 hi", "踩镲"]),
    ("drum_machine",   ["鼓机", "四四拍鼓机", "慵懒鼓机", "四四拍"]),
    ("drums_acoustic", ["鼓组", "军鼓", "切分鼓组", "碎拍鼓组", "底鼓", "四四拍底鼓", "反拍鼓", "双踩鼓", "爵士鼓", "kick", "snare", "鼓"]),
    ("percussion",     ["打击乐", "沙锤", "铃鼓", "拍手", "细碎打击", "碎拍打击", "拉丁打击", "手鼓", "非洲鼓",
                        "康加", "conga", "tambora", "surdo", "邦戈", "宝思兰", "太鼓", "塔布拉", "长鼓",
                        "定音鼓", "马林巴", "越南鼓", "鼓刷", "shaker", "bongo", "刮器", "刮响器", "dembow", "碎拍编程", "响葫芦"]),
    ("drum_machine",   []),  # placeholder（已在上面）

    ("guitar_slide",     ["滑音吉他", "slide guitar"]),
    ("guitar_distorted", ["失真吉他", "电吉他失真", "轻失真吉他", "雷鬼吉他 skank", "雷鬼吉他"]),
    ("guitar_rhythm",    ["节奏吉他"]),
    ("guitar_acoustic",  ["原声吉他", "尼龙弦吉他", "钢吉他", "环境吉他"]),
    ("guitar_electric",  ["电吉他长音"]),
    ("guitar_acoustic",  []),
    ("guitar_misc",      ["吉他", "guitar"]),  # 兜底（极少触发，上面已覆盖绝大多数）

    ("synth_chip",   ["芯片音色", "芯片音", "模拟芯片"]),
    ("synth_analog", ["模拟合成器", "模块合成器", "acid 303", "滤波合成"]),
    ("synth_lead",   ["合成 lead", "合成主音", "合成器 lead", "明亮 lead", "高音主旋", "闪烁合成", "失真合成器", "lead 旋律"]),
    ("synth_fm",     ["fm 钟声", "钟声", "三角波", "方波", "脉冲波", "编钟"]),
    ("synth_pad",    ["合成 pad", "合成器 pad", "空灵 pad", "弦乐垫", "弦乐pad", "混响墙", "合唱 pad", "pad"]),
    ("synth_misc",   ["合成器", "合成点缀", "合成器 synth", "合成弦乐"]),

    ("vocal_tuned",  ["人声 auto-tune", "autotune", "auto-tune"]),
    ("vocal_choir",  ["人声合唱", "合唱", "多部和声", "和声人声"]),
    ("vocal_chop",   ["人声切片", "人声 chop", "memphis 人声切片", "切碎人声切片", "失真人声切片"]),
    ("vocal_full",   ["人声", "vocal", "采样人声", "深情人声采样", "低吟人声", "冷峻人声",
                      "尖啸人声", "柔和人声", "气声人声", "颤音人声", "人声采样"]),

    ("sfx_noise",     ["唱片噪音", "采样唱片噪音", "黑胶噪点", "黑胶采样", "噪声通道", "数字失真",
                       "比特压缩", "电路弯折", "电路板 fx", "噪音", "噪声"]),
    ("sfx_glitch",    ["故障 fx", "故障音 glitch", "glitch"]),
    ("sfx_cinematic", ["激光音效", "减速采样", "失真采样", "破碎采样", "电影采样", "田野录音",
                       "环境音", "磁带 loop", "环境采样", "采样切片", "fx 音效", "fx", "音效", "采样"]),

    ("keys_piano",   ["钢琴", "原声钢琴", "电钢", "电钢琴", "踏板电钢", "键盘", "keys", "montuno", "rhodes"]),
    ("accordion",    ["手风琴"]),
    ("organ",        ["管风琴", "教堂管风琴", "风琴"]),
    ("harp",         ["竖琴", "harp", "水晶碗"]),
    ("strings",      ["弦乐", "弦乐采样", "弦乐切片", "弦乐四重奏", "小提琴", "大提琴", "管弦", "string quartet"]),
    ("brass",        ["铜管", "小号", "长号", "法国号", "萨克斯", "铜管 stab", "bagpipe"]),
    ("woodwind",     ["长笛", "笛子", "箫", "笙", "葫芦丝", "巴乌", "埙", "篠笛", "尺八", "奈伊笛",
                     "印度长笛", "锡哨", "唢呐", "木管", "flute", "bansuri", "shakuhachi", "tin whistle", "zurna", "ney", "shinobue",
                     "口琴", "harmonica", "单簧管", "双簧管", "大笒", "daegeum"]),
    ("ethnic_plucked",["三味线", "冬不拉", "乌德琴", "玄琴", "伽倻琴", "卡农", "阮", "萨摩琵琶", "萨罗德琴",
                      "西塔琴", "古筝", "古琴", "琵琶", "箜篌", "班卓琴", "曼陀林", "筝", "koto", "sitar", "sarod", "shamisen", "民族乐器"]),
    ("ethnic_bowed",  ["马头琴", "奚琴", "胡弓", "haegeum", "kokyū", "二胡"]),
]

# 去掉占位空规则
RULES = [r for r in RULES if r[1]]


def load_words():
    vocab = Counter()
    for f in sorted(glob.glob(os.path.join(MUSIC_STYLES, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for inst in (d.get("instruments") or []):
            vocab[inst.strip()] += 1
    return vocab


def match_class(word: str) -> str | None:
    s = word.lower()
    for cls, kws in RULES:
        for kw in kws:
            if kw.lower() in s:
                return cls
    return None


def main():
    vocab = load_words()
    word_map = OrderedDict()
    unmapped = []
    cls_words: dict[str, list[str]] = {c: [] for c in CLASSES}
    cls_counts: dict[str, int] = {c: 0 for c in CLASSES}

    for w, c in vocab.items():
        cls = match_class(w)
        if cls is None:
            unmapped.append(w)
            continue
        word_map[w] = cls
        cls_words[cls].append(w)
        cls_counts[cls] += c

    if unmapped:
        print(f"[ERROR] 有 {len(unmapped)} 个词未匹配到任何类目：")
        for u in unmapped:
            print("   -", u)
        raise SystemExit(1)

    # 组装输出
    classes_out = OrderedDict()
    for cls, meta in CLASSES.items():
        m = dict(meta)
        m["words"] = sorted(cls_words[cls])
        m["style_count"] = cls_counts[cls]
        m["prefer_subdirs"] = PREFER_SUBDIRS.get(cls, [])
        classes_out[cls] = m

    out = {
        "version": 1,
        "description": "musickit 规范乐器分类体系：由 G:\\tools\\music 的 63 风格池 242 乐器词归并而成",
        "pools": ["bass", "drum", "guita", "cowbell", "synth", "acapella", "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"],
        "canonical_classes": classes_out,
        "word_map": word_map,
        "stats": {
            "total_words": len(vocab),
            "total_occurrences": sum(vocab.values()),
            "classes": len(CLASSES),
            "available_classes": sum(1 for c in CLASSES.values() if c["available"]),
            "unavailable_classes": sum(1 for c in CLASSES.values() if not c["available"]),
        },
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"已写入 {OUT}")
    print(f"  乐器词总数: {len(vocab)}（全部归类，零遗漏）")
    print(f"  规范类目数: {len(CLASSES)}（可用 {out['stats']['available_classes']} / 无样本 {out['stats']['unavailable_classes']}）")
    print(f"  覆盖风格池出现次数: {sum(vocab.values())}")


if __name__ == "__main__":
    main()
