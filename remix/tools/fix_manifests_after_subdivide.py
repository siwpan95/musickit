"""Recovery after the interrupted subdivide_manifests.py --apply run.

The apply moved most files into taxonomy sub-folders but crashed (sandbox
safe-delete shim broke shutil.move's unlink fallback) BEFORE writing any
manifest and BEFORE moving the last ~281 root files (guita 259 + drum 22).

This script, run AFTER that crash, completes the job idempotently:
  Phase A: move any remaining pool-root audio file to its taxonomy sub-folder
           (manifested -> classifier target incl. cross-pool rescue;
            disk_only  -> <pool>_misc). Uses os.replace (atomic, no unlink).
  Phase B: rebuild each pool manifest from disk: subcategory = immediate
           sub-folder; original metadata recovered from old manifests by
           basename (so guita->keys / synth->bass rescue metadata survives).

Idempotent: re-running after success is a no-op (root empty, manifests match).
Usage:
  python fix_manifests_after_subdivide.py --dry    # print plan only
  python fix_manifests_after_subdivide.py          # execute
"""
import os
import json
import argparse
import importlib.util

ROOT = r"G:\musickit"
SUBDIVIDE_POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx"]
AEXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")

# load classifiers from the original subdivider
spec = importlib.util.spec_from_file_location(
    "subdiv", os.path.join(ROOT, "remix", "tools", "subdivide_manifests.py"))
subdiv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subdiv)
CLASSIFIERS = subdiv.CLASSIFIERS


def load_manifest(pool):
    mp = os.path.join(ROOT, pool, "manifest.json")
    if os.path.exists(mp):
        try:
            return json.load(open(mp, encoding="utf-8")).get("entries", [])
        except Exception:
            return []
    return []


# global basename -> old entry (preserves original/source_pack across rescues)
GLOBAL = {}
for p in SUBDIVIDE_POOLS:
    for e in load_manifest(p):
        GLOBAL.setdefault(e.get("file"), e)


def move_file(src, dst, dry):
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    if os.path.exists(dst):
        if dry:
            print(f"    [dry] DUP drop src: {src}")
            return
        try:
            os.remove(src)
        except Exception as ex:
            print(f"  [DUP-REMOVE FAIL] {src}: {ex}")
        return
    if dry:
        print(f"    [dry] MOVE {os.path.basename(src)} -> {os.path.relpath(dst, ROOT)}")
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.replace(src, dst)


def phase_a(dry):
    print("=== Phase A: move remaining root files ===")
    total = 0
    for pool in SUBDIVIDE_POOLS:
        pdir = os.path.join(ROOT, pool)
        for name in sorted(os.listdir(pdir)):
            fp = os.path.join(pdir, name)
            if os.path.isdir(fp) or not name.lower().endswith(AEXT):
                continue
            old = GLOBAL.get(name)
            if old:
                tpool, tsub = CLASSIFIERS[pool](old)
            else:
                tpool, tsub = pool, f"{pool}_misc"
            dst = os.path.join(ROOT, tpool, tsub, name)
            if dry:
                print(f"  {pool}: {name} -> {tpool}/{tsub}")
            move_file(fp, dst, dry)
            total += 1
    print(f"Phase A: {total} root files handled" + (" (DRY)" if dry else ""))


def phase_b(dry):
    print("=== Phase B: rebuild manifests from disk ===")
    for pool in SUBDIVIDE_POOLS:
        pdir = os.path.join(ROOT, pool)
        new_entries = []
        seen = set()
        for _root, _dirs, _files in os.walk(pdir):
            rel = os.path.relpath(_root, pdir)
            if rel in (".", ""):
                sub = f"{pool}_misc"
            else:
                sub = rel.split(os.sep)[0]
            for f in _files:
                if not f.lower().endswith(AEXT):
                    continue
                key = (sub, f)
                if key in seen:
                    continue
                seen.add(key)
                old = GLOBAL.get(f)
                e = dict(old) if old else {"file": f}
                e["file"] = f
                e["subcategory"] = sub
                new_entries.append(e)
        if dry:
            print(f"  {pool}: would write {len(new_entries)} entries")
            continue
        mp = os.path.join(pdir, "manifest.json")
        json.dump({"generated_by": "fix_manifests_after_subdivide.py",
                   "entries": new_entries},
                  open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  {pool}: {len(new_entries)} entries written")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    phase_a(args.dry)
    phase_b(args.dry)
    print("Done" + (" (DRY)" if args.dry else ""))


if __name__ == "__main__":
    main()
