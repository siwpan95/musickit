"""Phase 6：把 XAM Sample Pack Vol.3 按 taxonomy 子类 COPY 进 musickit。

源: G:\\BaiduNetdiskDownload\\XAM.Sample.Pack3\\XAM Sample Pack Vol.3
目标: G:\\music\\musickit\\<pool>\\<sub>\\

采用 COPY 模式（保留原始素材包，不移动）。按文件名/子目录路由到对应子类，
重复文件（同名）跳过。每复制一个文件，向目标池 manifest.json 合并一条
source_pack="XAM Sample Pack Vol.3" 的条目（含 subcategory 字段）。

用法:
  python ingest_xam_pack.py            # 执行 COPY + 更新 manifest
  python ingest_xam_pack.py --dry     # 仅打印将复制的文件数，不落盘
"""
import os
import json
import shutil
import argparse

SRC = r"G:\BaiduNetdiskDownload\XAM.Sample.Pack3\XAM Sample Pack Vol.3"
ROOT = r"G:\music\musickit"
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
SRC_PACK = "XAM Sample Pack Vol.3"


def has(s, *words):
    s = (s or "").lower()
    return any(w.lower() in s for w in words)


# (xam_relative_glob_dir, target_pool, target_sub, subcategory_for_entry)
# 顺序即优先级；Extra 用关键字二次路由
ROUTES = [
    ("acapellas", "acapella", "vocal_full", "vocal_full"),
    ("bass/808", "bass", "808_bass", "808_bass"),
    ("bass/Plucks", "bass", "bass_guitar", "bass_guitar"),
    ("bass/Reese", "bass", "sub_bass", "sub_bass"),
    ("fills", "drum", "drums_acoustic", "drums_acoustic"),
    ("hats/cymbals", "drum", "hihat", "hihat"),
    ("hats/hihats", "drum", "hihat", "hihat"),
    ("hats/open hats", "drum", "hihat", "hihat"),
    ("hats/Loops", "drum", "drums_acoustic", "drums_acoustic"),
    ("kick", "drum", "drum_machine", "drum_machine"),
    ("snares and claps", "drum", "drums_acoustic", "drums_acoustic"),
    ("percs and layers", "drum", "percussion", "percussion"),
    ("fx/risers", "sfx", "sfx_cinematic", "sfx_cinematic"),
    ("fx/sfx", "sfx", "sfx_cinematic", "sfx_cinematic"),
    ("fx/stomps and impacts", "sfx", "sfx_cinematic", "sfx_cinematic"),
    ("fx/transition", "sfx", "sfx_cinematic", "sfx_cinematic"),
    ("fx/vox", "acapella", "vocal_chop", "vocal_chop"),
    ("melodies", "synth", "synth_lead", "synth_lead"),
    ("samples", "synth", "synth_misc", "synth_misc"),
    ("one shots/Brazz", "brass", "brass", "brass"),
    ("one shots/Floots", "woodwind", "woodwind", "woodwind"),
    ("one shots/Guitar", "guita", "guitar_electric", "guitar_electric"),
    ("one shots/Plucks", "synth", "synth_misc", "synth_misc"),
]


def route_extra(name):
    """one shots/Extra 混合素材的关键字路由。"""
    n = name.lower()
    if has(n, "perc"):
        return ("drum", "percussion", "percussion")
    if has(n, "string"):
        return ("strings", "strings", "strings")
    if has(n, "harp"):
        return ("keys", "harp", "harp")
    if has(n, "boooom", "impact", "glass", "bell"):
        return ("sfx", "sfx_cinematic", "sfx_cinematic")
    # 其余（air/arcade/pitch 等）归为 sfx 杂项
    return ("sfx", "sfx_cinematic", "sfx_cinematic")


def collect():
    plan = []  # (src_file, pool, sub, subcat)
    for rel, pool, sub, subcat in ROUTES:
        d = os.path.join(SRC, rel)
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in sorted(files):
                if f.lower().endswith(AUDIO_EXT):
                    src = os.path.join(root, f)
                    tpool, tsub, tsubcat = pool, sub, subcat
                    # Extra 二次路由
                    if rel == "one shots/Extra":
                        tpool, tsub, tsubcat = route_extra(f)
                    plan.append((src, tpool, tsub, tsubcat))
    return plan


def load_manifest(pool):
    mp = os.path.join(ROOT, pool, "manifest.json")
    if not os.path.exists(mp):
        return []
    with open(mp, "r", encoding="utf-8") as f:
        return json.load(f).get("entries", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    plan = collect()
    print(f"XAM 待复制文件: {len(plan)}")
    by_target = {}
    for src, pool, sub, subcat in plan:
        by_target.setdefault((pool, sub), 0)
        by_target[(pool, sub)] += 1
    for (pool, sub), c in sorted(by_target.items()):
        print(f"  {pool:10s}/{sub:16s}: {c}")

    if args.dry:
        return

    # 按目标池聚合，便于合并 manifest
    per_pool = {}
    copied = 0
    skipped = 0
    for src, pool, sub, subcat in plan:
        fname = os.path.basename(src)
        dst = os.path.join(ROOT, pool, sub, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        entry = {
            "file": fname,
            "source_pack": SRC_PACK,
            "original": os.path.relpath(src, SRC),
            "original_rel": os.path.dirname(os.path.relpath(src, SRC)),
            "subcategory": subcat,
        }
        if os.path.exists(dst):
            skipped += 1
        else:
            shutil.copy2(src, dst)
            copied += 1
        per_pool.setdefault(pool, {})[fname] = entry

    # 合并写入各目标池 manifest
    for pool, entries in per_pool.items():
        existing = {e["file"]: e for e in load_manifest(pool)}
        existing.update(entries)
        mp = os.path.join(ROOT, pool, "manifest.json")
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        with open(mp, "w", encoding="utf-8") as f:
            json.dump({"generated_by": "ingest_xam_pack.py",
                       "entries": list(existing.values())},
                      f, ensure_ascii=False, indent=1)
        print(f"  {pool}/manifest.json 合并后 {len(existing)} 条")
    print(f"完成: 复制 {copied} 个，跳过同名 {skipped} 个。请运行 build_manifest_index.py。")


if __name__ == "__main__":
    main()
