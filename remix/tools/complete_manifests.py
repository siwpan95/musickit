"""Fill manifest gaps left by the two crashed+recovered subdivide runs.

The first crashed run moved `disk_only` numbered files into <pool>_misc sub-folders
but died before writing manifests; the second (completed) run only re-scanned pool
roots (already empty) so those moved files never got manifest entries. This script
appends a minimal entry for every disk audio file not yet covered by the manifest,
matching by RELATIVE PATH so acapella's nested-path entries aren't double-counted.

Append-only: existing entries (with metadata) are preserved; only missing files added.
"""
import os, json
ROOT = r"G:\music\musickit"
A = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff", ".aif")
POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx", "keys"]


def norm_rel(e):
    f = e.get("file", "")
    sub = e.get("subcategory")
    if sub:
        return (sub + "/" + f).replace("\\", "/")
    return f.replace("\\", "/")


for p in POOLS:
    pd = os.path.join(ROOT, p)
    mp = os.path.join(pd, "manifest.json")
    if not os.path.isdir(pd) or not os.path.exists(mp):
        continue
    d = json.load(open(mp, encoding="utf-8"))
    entries = list(d.get("entries", []))
    located = {norm_rel(e) for e in entries}
    added = 0
    for _r, _d, _f in os.walk(pd):
        rel = os.path.relpath(_r, pd).replace("\\", "/")
        sub = None if rel in (".", "") else rel.split("/")[0]
        for f in _f:
            if not f.lower().endswith(A):
                continue
            relpath = (sub + "/" + f) if sub else f
            if relpath in located:
                continue
            # acapella stores nested paths: skip if a located entry already ends with this basename
            if any(lp == f or lp.endswith("/" + f) for lp in located):
                continue
            entries.append({"file": relpath, "subcategory": sub})
            located.add(relpath)
            added += 1
    d["entries"] = entries
    json.dump(d, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{p}: +{added} entries (total {len(entries)})")
print("done")
