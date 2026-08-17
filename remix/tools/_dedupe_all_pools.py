#!/usr/bin/env python
"""Dedupe ALL pools by basename: keep one copy per basename, delete extras.

This is the generalization of _dedupe_acapella.py. It removes duplicates that
arose from re-ingesting already-present material into a different subdirectory
(the sync layer dedupes by basename globally, so extras stay orphaned on disk).

Usage:
    python _dedupe_all_pools.py --dry-run
    python _dedupe_all_pools.py --list    (write delete list, no deletion)
"""
import os
import sys
import collections

MUSICKIT = r"G:\musickit"
POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella", "animal",
         "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")


def main():
    dry = "--dry-run" in sys.argv
    lst = "--list" in sys.argv
    to_delete = []
    total_dup = 0
    for pool in POOLS:
        root = os.path.join(MUSICKIT, pool)
        if not os.path.isdir(root):
            continue
        by_name = collections.defaultdict(list)
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if fn.lower().endswith(AEXT):
                    by_name[fn].append(os.path.join(dp, fn))
        for fn, paths in by_name.items():
            if len(paths) > 1:
                # keep the lexicographically-first path, delete the rest
                paths_sorted = sorted(paths)
                total_dup += len(paths) - 1
                to_delete.extend(paths_sorted[1:])
    print(f"pools scanned: {len(POOLS)}  duplicate extras to delete: {len(to_delete)}")
    if dry:
        for p in to_delete[:8]:
            print("  would delete:", p.replace(MUSICKIT, ""))
    elif lst:
        with open(r"G:\tools\kontakt_transcode\alldup_del.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(to_delete))
        print("list written to G:\\tools\\kontakt_transcode\\alldup_del.txt")


if __name__ == "__main__":
    main()
