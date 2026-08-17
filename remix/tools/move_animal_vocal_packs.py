#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-5：把 animal 池中误入的真人声包移回 acapella 池（vocal_chops 子类）。

恢复「animal = 动物叫声、acapella = 人声」的语义约定。
只 move 不 delete；移动记录写入 archived/moved_vocal_packs_20260817.json，可回溯。

移动包（按 manifest source_pack 精确匹配）：
  - Loopmasters Vocals With Attitude WAV REX
  - Producer Loops Ethnic Pop Vocals MULTiFORMAT-DECiBEL
  - Stivenz Beats Vocal Chops

用法：
  python move_animal_vocal_packs.py --root G:\musickit            # dry-run
  python move_animal_vocal_packs.py --root G:\musickit --apply    # 执行移动 + 双 manifest 更新
"""
import argparse
import json
import os
import shutil

VOCAL_PACKS = [
    "Loopmasters Vocals With Attitude WAV REX",
    "Producer Loops Ethnic Pop Vocals MULTiFORMAT-DECiBEL",
    "Stivenz Beats Vocal Chops",
]


def _load(root: str, pool: str) -> dict | None:
    mp = os.path.join(root, pool, "manifest.json")
    if not os.path.isfile(mp):
        return None
    with open(mp, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def _save(root: str, pool: str, data: dict) -> None:
    with open(os.path.join(root, pool, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def plan_moves(root: str) -> list[dict]:
    """扫描 animal manifest，返回 [(entry, pack), ...] 移动计划。"""
    data = _load(root, "animal")
    if not data:
        return []
    out = []
    for e in data.get("entries", []):
        if isinstance(e, dict) and e.get("source_pack") in VOCAL_PACKS:
            out.append((e, e["source_pack"]))
    return out


def main():
    p = argparse.ArgumentParser(description="animal 池人声包迁回 acapella")
    p.add_argument("--root", default=r"G:\musickit", help="musickit 根目录")
    p.add_argument("--apply", action="store_true", help="执行移动与 manifest 更新")
    args = p.parse_args()

    plan = plan_moves(args.root)
    print(f"计划移动 {len(plan)} 个文件（{len(set(pk for _, pk in plan))} 个包）：")
    from collections import Counter
    for pk, n in Counter(pk for _, pk in plan).items():
        print(f"  - {pk}: {n}")

    if not args.apply:
        print("\n模式：dry-run（加 --apply 执行）")
        return

    records = []
    animal = _load(args.root, "animal")
    acapella = _load(args.root, "acapella")
    moved_files = set()
    for e, pk in plan:
        src = os.path.join(args.root, "animal", e["file"])
        dst_dir = os.path.join(args.root, "acapella", "vocal_chops", pk)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, e["file"])
        i = 1
        while os.path.exists(dst):
            stem, ext = os.path.splitext(e["file"])
            dst = os.path.join(dst_dir, f"{stem}_{i}{ext}")
            i += 1
        if os.path.isfile(src):
            shutil.move(src, dst)
            moved_files.add(e["file"])
        else:
            records.append({"pack": pk, "file": e["file"], "error": "源文件不存在"})
            continue
        new_e = dict(e)
        new_e["file"] = os.path.basename(dst)
        new_e["subcategory"] = f"vocal_chops/{pk}"
        new_e["license_tier"] = "pack"
        acapella.setdefault("entries", []).append(new_e)
        records.append({"pack": pk, "file": e["file"], "moved_to": dst})

    animal["entries"] = [e for e in animal.get("entries", [])
                         if e.get("file") not in moved_files
                         or not isinstance(e, dict)]
    _save(args.root, "animal", animal)
    _save(args.root, "acapella", acapella)

    rec_path = os.path.join(args.root, "archived", "moved_vocal_packs_20260817.json")
    os.makedirs(os.path.dirname(rec_path), exist_ok=True)
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    errs = [r for r in records if "error" in r]
    print(f"\n已移动 {len(records) - len(errs)} 个文件；记录：{rec_path}")
    for r in errs:
        print(f"  ⚠ {r['file']}: {r['error']}")


if __name__ == "__main__":
    main()
