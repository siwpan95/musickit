#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词驱动混音桥接器
================================
把 G:\\music\\musickit\\music（纯音乐风格提示词生成器）的结构化输出，
作为 G:\\music\\musickit\\remix（phonk 混音引擎）的「混音驱动」。

连接点：
  music_prompt_generator.generate()  ->  结构化提示词字典
      { label, subgenre, instruments[], bpm, moods[], elements[], scene }
            │  (本脚本做映射)
            ▼
  musickit.remix.main.run_remix(tracks, bpm, structure, ...)
            │
            ▼
  真实音频混音文件（WAV/MP3）

映射规则（由 G:\\music\\musickit\\instrument_taxonomy.json 驱动，消除“混用”）：
  - instruments[]  ->  每个乐器词经规范分类体系归并到 37 个类目，再精确映射到
                       musickit 池（bass/drum/guita/cowbell/synth/acapella/sfx）。
                       真人 acapella 池以 *vocal* 角色接入曲式模板的 vocal 层；
                       钢琴/弦乐/铜管/笛箫/民族乐器等 musickit 无样本的类目
                       会被跳过并记入 gaps，绝不假映射到错误池。
  - bpm            ->  目标混音速度（区间取整，钳制到 [70,200]）
  - moods/subgenre ->  曲式模板（classic_drop / ambient_ghost / loop_stack）

真人声接入说明：
  G:\\music\\musickit\\acapella 是「Coollider Acapellas Vols.1-42」解压后填充的
  真人整首人声池（分层目录 vol1..vol42），按 musickit 混音引擎的 *vocal* 角色接入。
  文件收集为递归（穿透 vol 子目录）。动物叫声已独立为 G:\\music\\musickit\\animal 池，
  不再冒充人声。

用法：
  # 生成 1 条 phonk 提示词并直接驱动混音
  python prompt_driven_remix.py -c phonk

  # 批量生成 3 条不同风格，各驱动一段混音
  python prompt_driven_remix.py -n 3 --out G:/music/musickit/music/prompt_mixes

  # 先由提示词工具导出 JSON，再喂给桥接器（解耦两类工具的版本）
  python music_prompt_generator.py -n 5 --export json -o prompts.json
  python prompt_driven_remix.py --prompt-json prompts.json

  # 只看映射结果，不真正混音
  python prompt_driven_remix.py -c trap --dry-run

  # 发布安全模式：仅用 free/pack 授权素材
  python prompt_driven_remix.py -c phonk --release-safe

依赖：运行需 F:\\Python314（pydub + numpy + audioop-lts），与 musickit 混音引擎一致。
"""

import argparse
import json
import os
import random
import re
import sys

# ---------------------------------------------------------------------------
# 路径装配
# ---------------------------------------------------------------------------
# 本脚本与 music_prompt_generator 同目录
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# 整合后 music/ 位于 musickit 根下：默认取 music/ 的上级目录为素材根；环境变量仍可覆盖
MUSICKIT_ROOT = os.environ.get("MUSICKIT_ROOT") or os.path.dirname(_THIS_DIR)
# musickit 混音引擎目录
REMIX_DIR = os.path.join(MUSICKIT_ROOT, "remix")

# 在 import musickit 的 main 之前，先把素材根目录钉死，避免被默认推算带偏
os.environ["MUSICKIT_ROOT"] = MUSICKIT_ROOT

sys.path.insert(0, _THIS_DIR)          # music_prompt_generator
sys.path.insert(0, REMIX_DIR)          # musickit.remix.main

import music_prompt_generator as mpg   # noqa: E402

# 用 importlib 按路径加载 musickit 的 main，避免与任何同名模块冲突
import importlib.util as _ilu          # noqa: E402
_spec = _ilu.spec_from_file_location("musickit_remix_main", os.path.join(REMIX_DIR, "main.py"))
_m = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_m)
run_remix = _m.run_remix
pick_loop_candidate = _m.pick_loop_candidate
_m_filter_release_safe = _m._filter_release_safe


# ---------------------------------------------------------------------------
# 乐器词 -> musickit 规范分类体系（由 G:\music\musickit\instrument_taxonomy.json 驱动）
# ---------------------------------------------------------------------------
# taxonomy 把 music 工具的 242 个自由文本乐器词归并为 37 个规范类目，
# 每类精确映射到 musickit 池 + 子类别 + 是否有样本。桥接器不再把不同家族
# 压进 7 个粗池，从而消除「混用」。
_TAXONOMY_PATH = os.path.join(MUSICKIT_ROOT, "instrument_taxonomy.json")
with open(_TAXONOMY_PATH, "r", encoding="utf-8") as _f:
    _TAX = json.load(_f)
_WORD_MAP = _TAX["word_map"]            # 原始乐器词 -> 规范类目
_CLASSES = _TAX["canonical_classes"]    # 规范类目 -> {pool, subcategory, available, mixer_role, ...}
# 按词长降序匹配，保证具体词优先（如 “808 贝斯” 先于 “贝斯”）
_WORDS_BY_LEN = sorted(_WORD_MAP.keys(), key=len, reverse=True)


def map_instrument(inst: str) -> dict | None:
    """将一条乐器描述串映射到 musickit 规范类目。

    Returns:
        {"class", "pool", "available", "mixer_role"} 或 None（无匹配）。
        mixer_role 是送入混音引擎的角色层键（vocal 类目统一为 "vocal"）。
    """
    s = inst.lower()
    for w in _WORDS_BY_LEN:
        if w.lower() in s:
            cls = _WORD_MAP[w]
            meta = _CLASSES[cls]
            return {
                "class": cls,
                "pool": meta.get("pool"),
                "available": meta.get("available", False),
                "mixer_role": meta.get("mixer_role", meta.get("pool")),
                "prefer_subdirs": meta.get("prefer_subdirs") or [],
            }
    return None


# ---------------------------------------------------------------------------
# 文件收集（递归，穿透 acapella 的 vol 子目录）
# ---------------------------------------------------------------------------
_AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff")


def collect_audio(category_dir: str) -> list[str]:
    """递归收集目录下所有音频文件（含子目录）。"""
    out: list[str] = []
    if not os.path.isdir(category_dir):
        return out
    for root, _dirs, files in os.walk(category_dir):
        for f in sorted(files):
            if f.lower().endswith(_AUDIO_EXTS):
                out.append(os.path.join(root, f))
    return out


def collect_for_pool(pool: str) -> list[str]:
    """按池名收集文件（vocal 类目统一从 acapella 池取，不再回落 animal 池）。"""
    if not pool:
        return []
    return collect_audio(os.path.join(MUSICKIT_ROOT, pool))


# ---------------------------------------------------------------------------
# 曲式模板选择（mood/subgenre/label -> structure key）
# 规则外置为 structure_moods.json（与本脚本同目录），关键词表不再散落在代码里。
# ---------------------------------------------------------------------------
_STRUCTURE_RULES_PATH = os.path.join(_THIS_DIR, "structure_moods.json")
with open(_STRUCTURE_RULES_PATH, "r", encoding="utf-8") as _f:
    _STRUCTURE_RULES = json.load(_f)


def choose_structure(label: str, subgenre: str, moods: list[str]) -> str:
    """按 structure_moods.json 关键词表选择曲式模板（order 首中即停）。"""
    blob = " ".join([label, subgenre] + list(moods)).lower()
    for key in _STRUCTURE_RULES.get("order",
                                    ["ambient_ghost", "classic_drop", "loop_stack"]):
        if any(w in blob for w in _STRUCTURE_RULES.get(key, [])):
            return key
    return _STRUCTURE_RULES.get("default", "classic_drop")


# ---------------------------------------------------------------------------
# 提示词 -> 混音参数
# ---------------------------------------------------------------------------
_LOOP_HINT_RE = re.compile(r"loop|_lp\b", re.I)
_BPM_HINT_RE = re.compile(r"\d{2,3}\s*bpm", re.I)
_NOTE_HINT_RE = re.compile(r"(^|[^a-z0-9])([a-g](?:#|b)?\d)([^a-z0-9]|$)", re.I)

# 旋律层角色：选音时优先 loop 类素材，避免单音采样被当 loop 循环
_MELODIC_ROLES = {"guita", "synth", "keys", "strings", "brass", "woodwind", "ethnic"}


def _loop_preferring(files: list[str],
                     entries: dict[str, dict] | None = None) -> list[str]:
    """旋律层选音偏好（三级回退）：loop/BPM 显式素材 > content_kind=loop >
    非单音采样 > 全量。

    单音采样（如 "EHn_susDyn_1-127_D3 - Group 1.wav"、"Basic Piano C2"）当 loop
    循环会产生随机音高、与其它层不协和；此函数把风险从「随机命中」降为「最后回退」。
    entries 为池 manifest 条目（{basename: entry}），提供 content_kind 形态判定。
    """
    if not files:
        return files
    tier1 = [f for f in files if _LOOP_HINT_RE.search(f) or _BPM_HINT_RE.search(f)]
    if tier1:
        return tier1
    if entries:
        tier2 = [f for f in files
                 if (entries.get(os.path.basename(f)) or {}).get("content_kind") == "loop"]
        if tier2:
            return tier2
    tier3 = [f for f in files if not _NOTE_HINT_RE.search(os.path.basename(f))]
    if tier3:
        return tier3
    return files


def _prefer_subdirs(files: list[str], pool: str, subs: list[str]) -> list[str]:
    """优先返回位于 taxonomy prefer_subdirs 子目录中的文件；无命中则全量回退。

    例如 woodwind 类目 prefer ["woodwind", "recorder"]：优先取爬虫入库的成品曲
    子目录，避开 15k 个管弦单音采样；keys_piano 优先 piano/ 子目录。
    """
    if not files or not subs:
        return files
    pool_dir = os.path.join(MUSICKIT_ROOT, pool)
    out = [f for f in files
           if os.path.relpath(f, pool_dir).split(os.sep)[0] in subs]
    return out or files


def _pool_entries() -> dict[str, dict[str, dict]]:
    """加载各素材池 manifest 条目：{pool: {basename: entry}}（授权层级过滤用）。"""
    out: dict[str, dict[str, dict]] = {}
    for pool in _TAX.get("pools", []):
        mp = os.path.join(MUSICKIT_ROOT, pool, "manifest.json")
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            for e in data.get("entries", []):
                if isinstance(e, dict) and e.get("file"):
                    out.setdefault(pool, {})[e["file"]] = e
        except Exception:
            pass
    return out


def prompt_to_mix_params(data: dict, rng: random.Random,
                         max_tracks: int = 5, add_skeleton: bool = True,
                         release_safe: bool = False):
    """把一条提示词字典转换为 run_remix 的调用参数。

    Returns:
        dict: { bpm, structure, tracks:[(cat,path),...], note }
    """
    # 1) BPM
    bpm = None
    raw_bpm = (data.get("bpm") or "").strip()
    nums = [int(x) for x in __import__("re").findall(r"\d+", raw_bpm)]
    if nums:
        bpm = max(70, min(200, nums[0]))

    # 2) 乐器 -> 规范类目 -> 按 mixer_role 抽文件（同一角色只取 1 条，避免重复家族）
    entries = _pool_entries()
    role_files: dict[str, list[str]] = {}
    role_pools: dict[str, str] = {}
    gaps: list[str] = []          # musickit 无样本 / 无匹配，被跳过的乐器
    for inst in data.get("instruments", []):
        m = map_instrument(inst)
        if m is None:
            gaps.append(f"{inst} [无匹配]")
            continue
        if not m["available"]:
            # 有规范类目但 musickit 没有真实样本：记录缺口，不假映射到错误池
            gaps.append(f"{inst} [{m['class']}:无样本]")
            continue
        role = m["mixer_role"]
        if role not in role_files:
            files = collect_for_pool(m["pool"])
            if release_safe:
                files = _m_filter_release_safe(files, m["pool"], entries, [])
            # 先按 taxonomy prefer_subdirs 收窄到对应子目录（如 808 贝斯 → 808_bass/），
            # 旋律层再优先 loop 类素材；鼓/贝斯在抽取时按引擎口径保底 >=1 小节
            files = _prefer_subdirs(files, m["pool"], m.get("prefer_subdirs") or [])
            if role in _MELODIC_ROLES:
                files = _loop_preferring(files, entries.get(m["pool"]))
            if not files:
                gaps.append(f"{inst} [空池 {m['pool']}]")
                continue
            role_files[role] = files
            role_pools[role] = m["pool"]
    # 每个命中的角色抽 1 条（鼓/贝斯骨架角色保底 >=1 小节 loop）
    tracks: list[tuple[str, str]] = []
    seen_roles = set()
    for role, files in role_files.items():
        if role in ("drum", "bass"):
            path = pick_loop_candidate(files, bpm or 120, rng,
                                       entries.get(role_pools[role]))
        else:
            path = rng.choice(files)
        if path:
            tracks.append((role, path))
            seen_roles.add(role)

    # 3) 节奏骨架兜底：保证至少有鼓 + 贝斯，否则听感太空（同样保底 >=1 小节 loop）
    if add_skeleton:
        for sk in ("drum", "bass"):
            if sk not in seen_roles:
                files = collect_for_pool(sk)
                if release_safe:
                    files = _m_filter_release_safe(files, sk, entries, [])
                path = (pick_loop_candidate(files, bpm or 120, rng, entries.get(sk))
                        if files else None)
                if path:
                    tracks.append((sk, path))
                    seen_roles.add(sk)

    # 4) 上限裁剪（引擎最多 8 轨）
    max_tracks = max(1, min(max_tracks, 8))
    tracks = tracks[:max_tracks]

    # 5) 曲式
    structure = choose_structure(data.get("label", ""),
                                data.get("subgenre", ""),
                                data.get("moods", []))

    return {
        "bpm": bpm,
        "structure": structure,
        "tracks": tracks,
        "note": f"instruments={data.get('instruments')}",
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# 提示词来源
# ---------------------------------------------------------------------------
def _normalize_prompt(entry: dict) -> dict:
    """把一条提示词归一化为桥接器内部使用的结构化字典。

    兼容两种来源：
      - music_prompt_generator.generate() 的直接产物（label + instruments 列表）
      - music_prompt_generator --export json 的扁平产物
        （style + instruments 为「、」连接字符串 + prompt 为提示词文本）
    """
    # 已是结构化形态
    if "label" in entry and isinstance(entry.get("instruments"), list):
        return entry

    def _split(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [x for x in v.split("、") if x.strip()]
        return []

    return {
        "label": entry.get("style") or entry.get("label") or "",
        "subgenre": entry.get("subgenre") or "",
        "instruments": _split(entry.get("instruments")),
        "scale": entry.get("scale") or "",
        "moods": _split(entry.get("moods")),
        "elements": _split(entry.get("elements")),
        "scene": entry.get("scene") or "",
        "bpm": entry.get("bpm") or "",
        "sentence": entry.get("prompt") or entry.get("sentence") or "",
        "fusion": bool(entry.get("fusion", False)),
        "fusion_with": entry.get("fusion_with") or "",
    }


def load_prompts_from_json(path: str) -> list[dict]:
    """读取 music_prompt_generator --export json 的产物，归一化为结构化列表。

    兼容两种外层结构：扁平数组，或含 prompts/results/items 字段的包裹对象。
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        raw = data
    else:
        raw = None
        for key in ("prompts", "results", "items"):
            if isinstance(data.get(key), list):
                raw = data[key]
                break
        if raw is None:
            raise ValueError(f"无法从 {path} 解析提示词列表")
    return [_normalize_prompt(e) for e in raw]


def _random_mixer_slug(rng: random.Random) -> str | None:
    """从 burbidge_album/mixer_styles.py 的共享风格注册表随机取一位混音师。"""
    try:
        bp = os.path.join(MUSICKIT_ROOT, "burbidge_album")
        if bp not in sys.path:
            sys.path.insert(0, bp)
        import mixer_styles as ms
        return rng.choice(ms.SLUGS)
    except Exception:
        return None


def generate_prompts(n: int, category: str | None, fusion: bool,
                     seed: int | None) -> list[dict]:
    profile = None
    if category:
        if category not in mpg.STYLE_BY_KEY:
            avail = ", ".join(mpg.STYLE_BY_KEY.keys())
            raise SystemExit(f"未知分类 '{category}'，可用：{avail}")
        profile = mpg.STYLE_BY_KEY[category]
    return mpg.batch_generate(n, profile, dedup=True, fusion=fusion,
                              english=False, seed=seed)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="提示词驱动混音：把 music 工具的风格提示词转为 musickit 真实混音",
    )
    # 提示词来源（二选一）
    p.add_argument("-c", "--category", type=str, default=None,
                   help="指定风格分类 key（同 music_prompt_generator）")
    p.add_argument("-n", "--num", type=int, default=1,
                   help="生成并驱动的提示词/混音条数（默认 1）")
    p.add_argument("--fusion", action="store_true",
                   help="跨类融合生成提示词")
    p.add_argument("--seed", type=int, default=None,
                   help="随机种子（提示词与选曲均可复现）")
    p.add_argument("--prompt-json", type=str, default=None,
                   help="改用已导出的提示词 JSON 驱动（跳过生成）")
    # 混音控制
    p.add_argument("--max-tracks", type=int, default=5,
                   help="单条混音最多音轨数（默认 5，引擎上限 8）")
    p.add_argument("--no-skeleton", action="store_true",
                   help="不为缺失鼓/贝斯的提示词自动补节奏骨架")
    p.add_argument("--bars", type=int, default=32,
                   help="输出小节数（默认 32）")
    p.add_argument("--structure", type=str, default=None,
                   help="强制曲式模板（classic_drop/ambient_ghost/loop_stack）")
    p.add_argument("--out", type=str, default=os.path.join(_THIS_DIR, "prompt_mixes"),
                   help="混音输出目录")
    p.add_argument("--format", type=str, default="wav",
                   choices=["wav", "mp3", "ogg", "flac"],
                   help="输出格式（默认 wav）")
    p.add_argument("--dry-run", action="store_true",
                   help="只打印提示词->混音参数映射，不真正混音")
    p.add_argument("--mixer-style", type=str, default=None,
                   help="混音师风格着色（burbidge/ghenea/clearmountain/marroquin/pensado/"
                        "blake/lordalge/schmitt/mikedean/stent/random；默认不启用）")
    p.add_argument("--release-safe", action="store_true",
                   help="发布安全模式：仅用授权层级为 free/pack 的素材（restricted/unknown 剔除）")
    p.add_argument("--report", type=str, default=None,
                   help="把 提示词->输出文件 的对照写进该 JSON")
    # S3 声明式入口：风格池插件清单（style_plugin 协议）
    p.add_argument("--list-styles", action="store_true",
                   help="列出风格池插件清单（声明式入口，不混音）")
    args = p.parse_args()

    if args.list_styles:
        from style_plugin import StyleRegistry
        reg = StyleRegistry()
        reg.load_all()
        for d in reg.dump():
            print("  %-22s v%s  %-12s %s  (%d 子类)" % (d["key"], d["version"], d["bpm"], d["label"], d["subgenres"]))
        print("共 %d 个风格插件" % len(reg))
        return 0

    # S3：-c 风格 key 校验（fail-loud：未知 key 当场点名并给建议）
    if args.category:
        from style_plugin import StyleRegistry
        reg = StyleRegistry()
        reg.load_all()
        if not reg.has(args.category):
            import difflib
            guess = difflib.get_close_matches(args.category, reg.keys, n=3)
            print("[style_plugin] 未知风格 key '%s'，可用（前 5）：%s ..." % (args.category, ", ".join(reg.keys[:5])),
                  file=sys.stderr)
            if guess:
                print("[style_plugin] 你是指：%s？" % ", ".join(guess), file=sys.stderr)
            return 2

    # 取提示词
    if args.prompt_json:
        prompts = load_prompts_from_json(args.prompt_json)
        print(f"从 {args.prompt_json} 载入 {len(prompts)} 条提示词")
    else:
        prompts = generate_prompts(args.num, args.category,
                                   args.fusion, args.seed)
        print(f"生成 {len(prompts)} 条提示词")

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)
    results = []

    for i, data in enumerate(prompts, 1):
        mp = prompt_to_mix_params(data, rng,
                                  max_tracks=args.max_tracks,
                                  add_skeleton=not args.no_skeleton,
                                  release_safe=args.release_safe)
        if args.structure:
            mp["structure"] = args.structure
        mixer_slug = args.mixer_style
        if mixer_slug == "random":
            mixer_slug = _random_mixer_slug(rng)
        mp["mixer_style"] = mixer_slug
        if mixer_slug:
            print(f"  mixer-style = {mixer_slug}")
        label = data.get("label", "")
        print(f"\n【#{i}】{label} ｜ {data.get('subgenre','')}")
        print(f"  提示词：{data.get('sentence','')}")
        print(f"  驱动  -> BPM={mp['bpm']}  structure={mp['structure']}")
        for ci, (cat, path) in enumerate(mp["tracks"], 1):
            print(f"    {ci}. [{cat}] {os.path.basename(path)}")
        if mp.get("gaps"):
            print(f"  ⚠ 跳过（musickit 无样本/无匹配）：{mp['gaps']}")

        if args.dry_run:
            results.append({"prompt": data, "mapping": mp, "output": None})
            continue

        out = run_remix(
            count=len(mp["tracks"]),
            seed=args.seed,
            out_dir=args.out,
            fmt=args.format,
            bars=args.bars,
            bpm=mp["bpm"],
            structure=mp["structure"],
            tracks=mp["tracks"],
            release_safe=args.release_safe,
            mixer_style=mixer_slug,
        )
        results.append({"prompt": data, "mapping": mp, "output": out})
        print(f"  ✅ 混音已保存：{out}")

    if args.report:
        slim = [{
            "label": r["prompt"].get("label"),
            "bpm": r["mapping"]["bpm"],
            "structure": r["mapping"]["structure"],
            "mixer_style": r["mapping"].get("mixer_style"),
            "tracks": [list(t) for t in r["mapping"]["tracks"]],
            "gaps": r["mapping"].get("gaps", []),
            "output": r["output"],
        } for r in results]
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=2)
        print(f"\n报告已写入：{args.report}")

    print(f"\n完成：{len(results)} 条提示词驱动混音" +
          ("（dry-run）" if args.dry_run else ""))


if __name__ == "__main__":
    # Windows 控制台 GBK -> UTF-8，避免中文/emoji 输出报错
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
