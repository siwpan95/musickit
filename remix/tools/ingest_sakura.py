"""Phase 6b：把 Sakura (Singomakers Sakura House) 的新素材 COPY 进 musickit。

该包大部分（bass/drum/fx/vocal 循环）已在 musickit 中（source_pack=Sakura），
因此只取「尚未覆盖」的部分：
  - Koto 采样 -> ethnic/ethnic_plucked  (24 个，真正的新类目)
  - 其余 wav 按子目录路由到对应子类，basename 去重（已存在则跳过，避免重复）
跳过 .rx2 (REX2 非标准音频)。

用法:
  python ingest_sakura.py
  python ingest_sakura.py --dry
"""
import os
import json
import shutil
import argparse

SRC = r"G:\BaiduNetdiskDownload\1\Sakura\Singomakers Sakura House"
ROOT = r"G:\music\musickit"
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
SRC_PACK = "Singomakers Sakura House"


def has(s, *words):
    s = (s or "").lower()
    return any(w.lower() in s for w in words)


def route(rel_dir, name):
    low = name.lower()
    if has(low, "koto"):
        return ("ethnic", "ethnic_plucked", "ethnic_plucked")
    d = rel_dir.lower()
    if "bass" in d:
        return ("bass", "bass_guitar", "bass_guitar")
    if "drum" in d:
        return ("drum", "drums_acoustic", "drums_acoustic")
    if "vocal" in d:
        return ("acapella", "vocal_full", "vocal_full")
    if "fx" in d:
        return ("sfx", "sfx_cinematic", "sfx_cinematic")
    if "music" in d:
        return ("synth", "synth_misc", "synth_misc")
    if "one_shot" in d or "oneshot" in d:
        if has(low, "kick", "bd"):
            return ("drum", "drums_acoustic", "drums_acoustic")
        if has(low, "snare", "clap"):
            return ("drum", "drums_acoustic", "drums_acoustic")
        if has(low, "hat"):
            return ("drum", "hihat", "hihat")
        if has(low, "bass"):
            return ("bass", "bass_guitar", "bass_guitar")
        return ("synth", "synth_misc", "synth_misc")
    if "atmospheric" in d:
        return ("synth", "synth_pad", "synth_pad")
    return ("synth", "synth_misc", "synth_misc")


def collect():
    plan = []
    if not os.path.isdir(SRC):
        return plan
    for root, _dirs, files in os.walk(SRC):
        for f in sorted(files):
            if not f.lower().endswith(AUDIO_EXT):
                continue
            if f.lower().endswith(".rx2"):
                continue
            rel = os.path.relpath(root, SRC)
            pool, sub, subcat = route(rel, f)
            plan.append((os.path.join(root, f), pool, sub, subcat))
    return plan


def load_manifest(pool):
    mp = os.path.join(ROOT, pool, "manifest.json")
    if not os.path.exists(mp):
        return []
    with open(mp, "r", encoding="utf-8") as fh:
        return json.load(fh).get("entries", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    plan = collect()
    print(f"Sakura 待复制文件: {len(plan)}")
    by_target = {}
    for _s, pool, sub, _c in plan:
        by_target[(pool, sub)] = by_target.get((pool, sub), 0) + 1
    for (pool, sub), c in sorted(by_target.items()):
        print(f"  {pool:10s}/{sub:16s}: {c}")

    if args.dry:
        return

    per_pool = {}
    copied = skipped = 0
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

    for pool, entries in per_pool.items():
        existing = {e["file"]: e for e in load_manifest(pool)}
        existing.update(entries)
        mp = os.path.join(ROOT, pool, "manifest.json")
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump({"generated_by": "ingest_sakura.py",
                       "entries": list(existing.values())},
                      fh, ensure_ascii=False, indent=1)
        print(f"  {pool}/manifest.json 合并后 {len(existing)} 条")
    print(f"完成: 复制 {copied} 个，跳过同名 {skipped} 个。")


if __name__ == "__main__":
    main()
