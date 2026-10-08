#!/usr/bin/env python
"""Build per-container selective-unpack lists for Berlin Woodwinds nkx monoliths.

Input : <KONTAKT_TRANSCODE_ROOT>/bww1_lists/<container>.txt  (NkxTool list output)
Output: <KONTAKT_TRANSCODE_ROOT>/bww1_wanted/<container>.txt  (@filelist for NkxTool unpack)

Rules:  " - AB.ncw" mic only; articulation dir not legato/runs/transition;
        round robin rep1 only (or no rep marker).
"""
import collections
import glob
import os
import re

# 数据根**去符盘**（铁律 5）：优先环境变量 KONTAKT_TRANSCODE_ROOT，
# 未设置时用约定相对根（旧机为 <盘>:/notpython/kontakt_transcode）。
_KT_ROOT = os.environ.get("KONTAKT_TRANSCODE_ROOT", "kontakt_transcode")
SRC = os.path.join(_KT_ROOT, "bww1_lists")
DST = os.path.join(_KT_ROOT, "bww1_wanted")

BAD_ART = ("legato", "runs", "transition", "release", "looped", "loop", "portamento")
KEEP_HINTS = ("stacc", "marcato", "trill", "sus", "repetition", "pizzicato",
              "portato", "sfz", "accent", "tremolo", "short", "long", "sforz")


def art_ok(art: str) -> bool:
    a = art.lower()
    for b in BAD_ART:
        if b in a:
            return False
    for k in KEEP_HINTS:
        if k in a:
            return True
    return False


def main():
    os.makedirs(DST, exist_ok=True)
    total = kept = 0
    per = {}
    for fp in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
        base = os.path.splitext(os.path.basename(fp))[0]
        wanted = []
        with open(fp, encoding="utf-8-sig", errors="replace") as f:
            for ln in f:
                ln = ln.rstrip("\n").strip()
                if not ln:
                    continue
                total += 1
                if not ln.endswith(" - AB.ncw"):
                    continue
                parts = ln.split("\\")
                if len(parts) < 3 or not art_ok(parts[1]):
                    continue
                fn = parts[-1]
                m = re.search(r"_rep(\d+)_", fn)
                if m and int(m.group(1)) != 1:
                    continue
                wanted.append(ln)
        if wanted:
            with open(os.path.join(DST, base + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(wanted) + "\n")
        kept += len(wanted)
        per[base] = len(wanted)
    print(f"containers: {len(per)}  entries: {total}  wanted: {kept}")
    print("top containers:")
    for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {v:6d}  {k}")
    print("out ->", DST)


if __name__ == "__main__":
    main()
