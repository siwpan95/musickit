#!/usr/bin/env python
"""Dedupe the acapella pool by basename.

Keeps one copy per basename; for duplicates, prefers the pre-existing
historical location (vocal_full / root Coollider dirs) and deletes the
newly-ingested copies under acapella\acapella (this run's duplicate ingest).

Usage:
    python _dedupe_acapella.py --dry-run
    python _dedupe_acapella.py --apply
"""
import os
import sys
import collections
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

POOL = str(_MK_ROOT / "acapella")
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")

# keep-priority: a path is "preferred" if it is NOT under acapella\<acapella>
# (the first path component is the "acapella" subdir)
def preferred(path):
    rel = os.path.relpath(path, POOL).lower()
    return not rel.startswith("acapella" + os.sep)


def main():
    dry = "--dry-run" in sys.argv
    by_name = collections.defaultdict(list)
    for dp, _, fns in os.walk(POOL):
        for fn in fns:
            if not fn.lower().endswith(AEXT):
                continue
            by_name[fn].append(os.path.join(dp, fn))

    to_delete = []
    for fn, paths in by_name.items():
        if len(paths) == 1:
            continue
        keep = [p for p in paths if preferred(p)]
        if keep:
            # delete the non-preferred (acapella\acapella) copies
            for p in paths:
                if p not in keep:
                    to_delete.append(p)
        else:
            # all under acapella\acapella: keep first, delete rest
            for p in paths[1:]:
                to_delete.append(p)

    print(f"unique basenames: {len(by_name)}  total files: {sum(len(v) for v in by_name.values())}")
    print(f"to delete: {len(to_delete)}")
    dup_dirs = collections.Counter()
    for p in to_delete:
        dup_dirs[os.path.relpath(os.path.dirname(p), POOL)] += 1
    print("--- delete by dir ---")
    for k, v in dup_dirs.most_common(8):
        print(f"  {v:5d}  {k}")
    if not dry and to_delete:
        n = 0
        for p in to_delete:
            try:
                os.remove(p)
                n += 1
            except OSError as e:
                print("  remove fail", p, e)
        print(f"deleted {n} files")
    elif dry:
        print("(dry-run: no files deleted)")
        for p in to_delete[:5]:
            print("   would delete:", os.path.relpath(p, POOL))


if __name__ == "__main__":
    main()
