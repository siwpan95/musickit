#!/usr/bin/env python
"""Build a selective-extract list for Berlin Strings multi-volume zip.

Rules (all must match):
  1. path contains \\Samples\\ and ends with " - AB.ncw"  (AB mic only, 1 of 5 mics)
  2. articulation dir is NOT a legato/portamento/transition type
  3. filename keeps round robin rep1 only (drop rep2..), and no Cuttd/transition
  4. dynamic layer: keep only the LAST layer variant per (instrument, art, note)
     (filenames embed ranges like 64-127; identical prefixes differing only in
     the range -> keep one, prefer the louder/higher one)

Output: G:/tools/kontakt_transcode/bst_wanted.txt (7z @listfile format)
"""
import collections
import os
import re

LISTING = r"G:/tools/kontakt_transcode/bst_listing.txt"
OUT = r"G:/tools/kontakt_transcode/bst_wanted.txt"

# articulation-dir blacklist: legato-family / transitions / releases / loops
BAD_ART = ("legato", "portamento", "release", "releases", "looped", "loop",
           "transition", "trill_maj", "trill_min")  # measured trills are ok
# but keep these even if name contains the words above? no - hard exclude.
KEEP_HINTS = ("sustains", "sustain", "spiccato", "staccato", "pizzicato",
              "portato", "tremolo", "trills", "col legno", "harmonics",
              "aleatoric", "marcato", "sforzando", "bartok", "flautando",
              "ricochet", "saltando", "detache", "accent", "mute", "ponticello",
              "tasto")


def art_ok(art: str) -> bool:
    a = art.lower()
    for b in BAD_ART:
        if b in a:
            return False
    for k in KEEP_HINTS:
        if k in a:
            return True
    return False


def parse_paths():
    paths = []
    # 7z wrote the listing in the system ANSI codepage (GBK)
    with open(LISTING, encoding="gbk", errors="replace") as f:
        for line in f:
            if line.startswith("Path = "):
                paths.append(line[7:].rstrip("\n"))
    return paths


def main():
    paths = parse_paths()
    # stage 1: AB-mic ncw under Samples with valid articulation
    kept = []
    for p in paths:
        if not p.lower().endswith(" - ab.ncw"):
            continue
        parts = p.split("\\")
        if "Samples" not in parts:
            continue
        i = parts.index("Samples")
        if i + 2 >= len(parts):
            continue
        art = parts[i + 2]
        if not art_ok(art):
            continue
        fn = parts[-1]
        # drop round-robin reps beyond 1 (rep2, rep3, ...) but keep files with no rep marker
        m = re.search(r"_rep(\d+)_", fn)
        if m and int(m.group(1)) != 1:
            continue
        kept.append(p)

    # stage 2: one dynamic layer per (instrument, art, note): files identical
    # except for the "<range>" token collapse to one (prefer the louder layer).
    groups = collections.defaultdict(list)
    for p in kept:
        fn = os.path.basename(p)
        m = re.search(r"_(\d+-\d+)_([A-G][#b]?\d)\s+-\s+AB\.ncw$", fn, re.I)
        if m:
            key = p.replace(m.group(1), "", 1)  # drop range token, keep note
        else:
            key = p
        groups[key].append(p)

    final = []
    for key, ps in groups.items():
        if len(ps) == 1:
            final.append(ps[0])
        else:
            # prefer louder layer: larger first range number
            def loudness(p):
                m = re.search(r"_(\d+)-(\d+)_[A-G][#b]?\d\s+-\s+AB\.ncw$", os.path.basename(p), re.I)
                return int(m.group(1)) if m else -1
            final.append(sorted(ps, key=loudness, reverse=True)[0])

    # write in GBK: 7z reads listfiles in the system ANSI codepage
    with open(OUT, "w", encoding="gbk") as f:
        for p in sorted(final):
            f.write(p + "\n")
    print(f"stage1 (AB mic, non-legato art, rep1): {len(kept)}")
    print(f"stage2 (single dynamic layer):        {len(final)}")
    # per-instrument breakdown
    insts = collections.Counter()
    for p in final:
        parts = p.split("\\")
        insts[parts[parts.index("Samples") + 1]] += 1
    print("--- per instrument ---")
    for k, v in insts.most_common():
        print(f"{v:6d}  {k}")
    print("list ->", OUT)


if __name__ == "__main__":
    main()
