"""musical_key — 调性（key/scale）解析与兼容判定。

T2-1 的目标：让提示词里的 `scale` 真正影响选音。
最小可行的做法不是加 pitch-shift DSP（风险高），而是**先让调性不打架**：
按调性把候选素材分组，优先挑与目标调性兼容的，不兼容的降级使用并记录原因。

兼容规则（从宽到严，越靠前越优先）：
  1. 同调（tonic 相同 + mode 相同）           —— 完美
  2. 关系大小调（C major ↔ A minor）          —— 同音阶集合，等价
  3. 纯五度 / 纯四度关系（C ↔ G / C ↔ F）     —— 可共存，偶有摩擦
  4. 同主音大小调（C major ↔ C minor）        —— 色彩冲突但调心一致，可用
  其余视为不兼容（如小二度、三全音）—— 只在没有更好选择时使用。

全部用整数音级（0=C, 1=C#, …, 11=B），不引入重依赖。
"""
from __future__ import annotations

import re

SEMITONE = {
    "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3,
    "e": 4, "fb": 4, "e#": 5, "f": 5, "f#": 6, "gb": 6,
    "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10,
    "b": 11, "cb": 11,
}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_MAJOR_WORDS = ("major", "maj", "大调", "大")
_MINOR_WORDS = ("minor", "min", "小调", "小")

#: 兼容等级：越小越优先
RANK_SAME = 0
RANK_RELATIVE = 1
RANK_FIFTH = 2
RANK_PARALLEL = 3
RANK_INCOMPATIBLE = 9


def parse_key(text: str | None) -> tuple[int, str] | None:
    """解析 "Cm" / "C minor" / "F# major" / "A小调" → (音级, 'major'|'minor')。

    无法解析返回 None（调用方应视为「未指定调性」，不做任何过滤）。
    """
    if not text or not isinstance(text, str):
        return None
    s = text.strip().lower().replace("♯", "#").replace("♭", "b")
    if not s:
        return None

    # 先抓音名（可能在开头，也可能形如 "minor: a"）
    m = re.search(r"([a-g](?:#|b)?)", s)
    if not m:
        return None
    name = m.group(1)
    if name not in SEMITONE:
        return None
    pc = SEMITONE[name]

    mode = None
    if any(w in s for w in _MINOR_WORDS):
        mode = "minor"
    elif any(w in s for w in _MAJOR_WORDS):
        mode = "major"
    else:
        # 仅给音名（"C"）→ 默认大调；给 "Cm" 这种后缀 m
        tail = s[m.end():].strip()
        mode = "minor" if tail.startswith("m") and not tail.startswith("maj") else "major"
    return pc, mode


def to_pc(name: str | None) -> int | None:
    """音名 → 音级，支持等音（Eb 与 D# 同值）。无法识别返回 None。"""
    if not name or not isinstance(name, str):
        return None
    s = name.strip().lower().replace("♯", "#").replace("♭", "b")
    if s in SEMITONE:
        return SEMITONE[s]
    # 允许 "C#4" / "C minor" 之类带后缀的写法
    m = re.match(r"([a-g](?:#|b)?)", s)
    if m:
        return SEMITONE.get(m.group(1))
    return None


def relative_minor(pc: int) -> int:
    return (pc + 9) % 12


def relative_major(pc: int) -> int:
    return (pc + 3) % 12


def rank(a: tuple[int, str] | None, b: tuple[int, str] | None) -> int:
    """两调性的兼容等级（0 最好，9 不兼容）。任一方未知返回 RANK_INCOMPATIBLE 之外的「中性」。"""
    if not a or not b:
        return RANK_FIFTH  # 未知调性按「可接受」处理，不奖励也不严惩
    (pa, ma), (pb, mb) = a, b
    if pa is None or pb is None:
        # 缺主音（只有调式）→ 只能比色彩
        return rank_mode_only(ma, mb)

    if pa == pb and ma == mb:
        return RANK_SAME
    if ma != mb:
        # 关系大小调：大调 pc 的关系小调 = pc+9；小调 pc 的关系大调 = pc+3
        if ma == "major" and mb == "minor" and relative_minor(pa) == pb:
            return RANK_RELATIVE
        if ma == "minor" and mb == "major" and relative_major(pa) == pb:
            return RANK_RELATIVE
        # 同主音大小调
        if pa == pb:
            return RANK_PARALLEL
        return RANK_INCOMPATIBLE
    # 同 mode：五度圈相邻
    if (pb - pa) % 12 in (7, 5):
        return RANK_FIFTH
    return RANK_INCOMPATIBLE


def format_key(pc: int, mode: str) -> str:
    return f"{NAMES[pc % 12]} {mode}"


def format_short(pc: int, mode: str) -> str:
    return f"{NAMES[pc % 12]}{'m' if mode == 'minor' else ''}"


def is_compatible(a, b, max_rank: int = RANK_PARALLEL) -> bool:
    return rank(a, b) <= max_rank


# ---------------------------------------------------------------------------
# 调式族（prompt 的 `scale` 是调式名，不含主音 —— 如「小调」「多利亚」「五声」）
# ---------------------------------------------------------------------------
#: 大调色彩（含 Lydian / Mixolydian 这类大三度调式）
MODE_MAJOR_WORDS = ("大调", "利底亚", "混合利底亚", "伊奥尼亚",
                    "major", "lydian", "mixolydian", "ionian")
#: 小调色彩（含 Dorian / Phrygian / 布鲁斯 这类小三度调式）
MODE_MINOR_WORDS = ("小调", "多利亚", "弗里几亚", "爱奥利亚", "洛克里亚", "布鲁斯",
                    "和声小调", "旋律小调",
                    "minor", "dorian", "phrygian", "aeolian", "locrian", "blues",
                    "harmonic minor", "melodic minor")
#: 调式色彩中性/无法归类（五声、全音阶、无调性…）—— 不做偏好
MODE_NEUTRAL_WORDS = ("五声", "全音阶", "无调性", "变化音阶", "半音阶", "七声",
                      "pentatonic", "whole tone", "whole-tone", "atonal",
                      "altered", "chromatic", "七声音阶")

#: 形如 "Cm" / "C minor" / "F# major" / "A小调" 的完整调性（允许尾部一个「调」字）
_FULL_KEY_RE = re.compile(
    r"^\s*([a-g](?:#|b)?)\s*(?:m|maj|min|major|minor|小调|大调|调)?\s*$", re.I
)


def parse_mode_family(text: str | None) -> str | None:
    """从调式名判断色彩族：'major' / 'minor' / None（中性或无法判断）。"""
    if not text or not isinstance(text, str):
        return None
    s = text.strip().lower()
    if not s:
        return None
    # 先判中性：如「小调五声」同时含两族关键词时，五声更本质
    if any(w in s for w in MODE_NEUTRAL_WORDS) and not any(w in s for w in MODE_MINOR_WORDS):
        return None
    if any(w in s for w in MODE_MINOR_WORDS):
        return "minor"
    if any(w in s for w in MODE_MAJOR_WORDS):
        return "major"
    return None


def parse_target(text: str | None) -> tuple[int | None, str | None] | None:
    """解析「目标调性」：完整调性返回 (音级, mode)；仅调式返回 (None, mode)。

    为什么分两种：提示词的 `scale` 只给调式（「小调」「多利亚」），没有主音；
    命令行 `--key Cm` 才带主音。无法解析（如「无调性」「五声」）返回 None。
    """
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    if _FULL_KEY_RE.match(s):
        k = parse_key(s)
        if k:
            return k
    fam = parse_mode_family(s)
    if fam:
        return (None, fam)
    return None


def rank_mode_only(mode_a: str | None, mode_b: str | None) -> int:
    """只有调式、没有主音时的兼容度：同色彩最优，异色彩可接受。"""
    if not mode_a or not mode_b:
        return RANK_FIFTH
    return RANK_SAME if mode_a == mode_b else RANK_PARALLEL


def format_target(target: tuple[int | None, str | None] | None) -> str:
    if not target:
        return "未指定"
    pc, mode = target
    if pc is None:
        return f"{mode}（仅调式）"
    return format_key(pc, mode)
