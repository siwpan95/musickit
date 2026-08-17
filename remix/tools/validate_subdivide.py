"""Validate the post-subdivision state: every manifest entry's file exists on disk
at <pool>/<subcategory>/<file>, every disk audio file is manifested, and there are
no duplicate basenames within a pool."""
import os, json
ROOT = r"G:\musickit"
A = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff", ".aif", ".wma", ".alac")
POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx", "keys"]


def norm_rel(e):
    f = e.get("file", "")
    sub = e.get("subcategory")
    if sub:
        return (sub + "/" + f).replace("\\", "/")
    return f.replace("\\", "/")


total_orphan_entry = 0
total_unmanifested = 0
total_dup = 0
for p in POOLS:
    pd = os.path.join(ROOT, p)
    if not os.path.isdir(pd):
        continue
    mp = os.path.join(pd, "manifest.json")
    entries = json.load(open(mp, encoding="utf-8")).get("entries", []) if os.path.exists(mp) else []
    located = {norm_rel(e) for e in entries}

    disk_rel = []
    seen_basename = {}
    dup = []
    for _r, _d, _f in os.walk(pd):
        rel = os.path.relpath(_r, pd).replace("\\", "/")
        for f in _f:
            if not f.lower().endswith(A):
                continue
            relpath = rel + "/" + f if rel not in (".", "") else f
            disk_rel.append(relpath)
            base = os.path.basename(f)
            if base in seen_basename:
                dup.append((base, seen_basename[base], relpath))
            else:
                seen_basename[base] = relpath

    disk_set = set(disk_rel)
    orphan = located - disk_set            # entry points to missing file
    unmanifested = disk_set - located    # file on disk not in manifest

    print(f"== {p}: manifest={len(entries)} disk={len(disk_rel)} ==")
    if orphan:
        total_orphan_entry += len(orphan)
        print(f"  [ORPHAN ENTRY] {len(orphan)} (e.g. {list(orphan)[:3]})")
    if unmanifested:
        total_unmanifested += len(unmanifested)
        print(f"  [UNMANIFESTED] {len(unmanifested)} (e.g. {list(unmanifested)[:3]})")
    if dup:
        total_dup += len(dup)
        print(f"  [DUP ON DISK] {len(dup)} (e.g. {dup[:3]})")

print(f"\nSUMMARY: orphan_entries={total_orphan_entry} unmanifested={total_unmanifested} dup_on_disk={total_dup}")
print("OK" if (total_orphan_entry == 0 and total_unmanifested == 0 and total_dup == 0) else "ISSUES FOUND")
