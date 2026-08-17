#!/usr/bin/env python
"""Build per-container selective-unpack lists for Brass Band Soloists nkx.

Input : G:/tools/kontakt_transcode/brass_lists/<container>.txt
Output: G:/tools/kontakt_transcode/brass_wanted/<container>.txt

Rules:
  - prefer the "414" mic (main pair); skip CLOSE/FAR/M60L/M60R duplicates
  - round robin: keep RR1 only (or no-RR files)
  - articulation priority: Short/Accent/Sus (all), Leg main notes (sampled 1 per
    note+dynamic), skip SoftRel/HardRel (release tails)
"""
import collections
import glob
import os
import re

SRC = r"G:/tools/kontakt_transcode/brass_lists"
DST = r"G:/tools/kontakt_transcode/brass_wanted"

MICS = ("414", "CLOSE", "FAR", "M60L", "M60R")
KEEP_ALL = ("MIDShort", "MIDAccent", "MIDSus", "MIDHardRelRR")  # hard rel RR tiny
LEG_SAMPLE = ("LegNvb", "LegVib")


def classify(base: str):
    """Return (mic, art, rr, note_key) or None if not wanted."""
    stem = base[:-4]
    parts = stem.split("_")
    if len(parts) < 2:
        return None
    tok = parts[1]
    mic = next((m for m in MICS if tok.startswith(m)), None)
    if mic is None:
        mic = "414" if tok[0].isdigit() else None
    if mic != "414":
        return None
    m = re.search(r"RR(\d+)", stem)
    rr = int(m.group(1)) if m else 0
    if rr > 1:
        return None
    for a in KEEP_ALL:
        if a in tok:
            return (mic, "keep", rr, stem)
    for a in LEG_SAMPLE:
        if a in tok:
            return (mic, "leg", rr, stem)
    return None


def main():
    os.makedirs(DST, exist_ok=True)
    total = 0
    keep_n = leg_n = 0
    # group leg samples by (instrument, art, note) to sample 1 per group
    leg_groups = collections.defaultdict(list)
    per = {}
    for fp in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
        base_name = os.path.splitext(os.path.basename(fp))[0]
        wanted = []
        with open(fp, encoding="utf-8-sig", errors="replace") as f:
            for ln in f:
                ln = ln.rstrip("\n").strip()
                if not ln:
                    continue
                total += 1
                base = ln.split("\\")[-1]
                if not base.endswith(".ncw"):
                    continue
                r = classify(base)
                if r is None:
                    continue
                _, kind, rr, stem = r
                if kind == "keep":
                    wanted.append(ln)
                    keep_n += 1
                else:
                    # leg: key = instrument+art+note (drop dynamic range token)
                    m = re.search(r"_\d+_\d+_([A-G]#?\d)\.ncw$", base)
                    key = stem
                    if m:
                        key = stem.rsplit("_", 3)[0] + "_" + m.group(1)
                    leg_groups[key].append(ln)
        per[base_name] = len(wanted)
        if wanted:
            with open(os.path.join(DST, base_name + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(wanted) + "\n")

    # sample leg groups: first entry (RR1 / lower dynamic) per group
    leg_extra = collections.defaultdict(list)
    for key, items in leg_groups.items():
        leg_extra[os.path.basename(key)].append(items[0])
        leg_n += 1
    # append leg picks to the container where they belong (re-match by scanning again)
    leg_by_cont = collections.defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
        cname = os.path.splitext(os.path.basename(fp))[0]
        picked = set(v[0] for k, v in leg_groups.items() if v)
        with open(fp, encoding="utf-8-sig", errors="replace") as f:
            for ln in f:
                ln = ln.rstrip("\n").strip()
                if ln in picked:
                    leg_by_cont[cname].append(ln)
    for cname, items in leg_by_cont.items():
        out = os.path.join(DST, cname + ".txt")
        with open(out, "a", encoding="utf-8") as f:
            f.write("\n".join(items) + "\n")

    print(f"entries: {total}  keep: {keep_n}  leg sampled: {leg_n}")
    tot_wanted = 0
    for fp in glob.glob(os.path.join(DST, "*.txt")):
        with open(fp, encoding="utf-8") as f:
            tot_wanted += sum(1 for l in f if l.strip())
    print(f"total wanted: {tot_wanted}  -> {DST}")


if __name__ == "__main__":
    main()
