"""Repair acapella manifest: normalize 'file' to basename, dedupe path-formatted
orphans, preserve metadata, cover every on-disk file exactly once.

The original subdivision wrote 1489 entries whose 'file' field was a relative
PATH (e.g. 'Coollider presents - Acapellas vol1/01 - x.mp3') instead of a
basename. The engine indexes by basename, so those entries are dead. This
regenerates acapella/manifest.json keyed by basename, merging metadata from the
existing entry that matches each file's basename.
"""
import json, os
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")
POOL = "acapella"
pdir = str(_MK_ROOT / POOL)
mp = os.path.join(pdir, "manifest.json")
data = json.load(open(mp, encoding="utf-8"))
entries = data.get("entries", [])

# disk map: basename -> (subcategory, original_rel)
disk = {}
for r, _, n in os.walk(pdir):
    rel = os.path.relpath(r, pdir).replace("\\", "/")
    sub = "(root)" if rel == "." else rel
    for nm in n:
        if nm.lower().endswith(AEXT):
            disk[nm] = (sub, rel)

# best existing entry per basename (prefer exact-basename 'file' over path-form)
by_base = {}
for e in entries:
    f = e.get("file", "")
    base = os.path.basename(f)
    if not base:
        continue
    cur = by_base.get(base)
    if cur is None:
        by_base[base] = e
    elif f == base and cur.get("file") != base:
        by_base[base] = e  # prefer the properly-keyed entry

new_entries = []
for base, (sub, rel) in sorted(disk.items()):
    e = dict(by_base.get(base, {}))
    e["file"] = base
    e["subcategory"] = sub
    e["original_rel"] = e.get("original_rel") or rel
    if "source_pack" not in e:
        e["source_pack"] = "sync"
    if "original" not in e:
        e["original"] = base
    if "license" not in e:
        e["license"] = "see source"
    if "duration_s" not in e:
        e["duration_s"] = None
    new_entries.append(e)

data["entries"] = new_entries
data["generated_by"] = "repair_acapella_manifest (basename-normalized)"
json.dump(data, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"acapella repaired: {len(new_entries)} entries (was {len(entries)})")
orphan_before = sum(1 for e in entries if os.path.basename(e.get('file','')) not in disk)
print(f"orphan path-form entries dropped: {orphan_before}")
