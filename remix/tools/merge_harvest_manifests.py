"""Merge harvested on-disk files into per-pool manifest.json for affected pools.

For each pool: load existing {"entries":[...]} (or start empty), walk the pool
directory, and append manifest entries for disk files not already present
(matched by basename). Entry shape matches subdivide convention:
  {file: <basename>, subcategory: <subfolder or '(root)'>, source_pack, original, ...}

Affected pools: keys, strings (new), woodwind, ethnic.
"""
import json, os

MUSICKIT = r"G:\music\musickit"
POOLS = ["keys", "strings", "woodwind", "ethnic"]
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac")


def merge_pool(pool):
    pool_dir = os.path.join(MUSICKIT, pool)
    if not os.path.isdir(pool_dir):
        print(f"[skip] {pool}: no dir")
        return
    mp = os.path.join(pool_dir, "manifest.json")
    if os.path.exists(mp):
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "entries" not in data:
            data = {"generated_by": "merge_harvest", "entries": []}
    else:
        data = {"generated_by": "merge_harvest", "entries": []}

    existing = {e.get("file") for e in data["entries"] if isinstance(e, dict)}
    added = 0
    for root, dirs, names in os.walk(pool_dir):
        rel_dir = os.path.relpath(root, pool_dir).replace("\\", "/")
        sub = "(root)" if rel_dir == "." else rel_dir
        for n in sorted(names):
            if not n.lower().endswith(AEXT):
                continue
            if n in existing:
                continue
            data["entries"].append({
                "file": n,
                "subcategory": sub,
                "source_pack": "ondisk-harvest",
                "original": n,
                "original_rel": sub,
                "license": "Royalty-free (on-disk pack)",
                "duration_s": None,
            })
            existing.add(n)
            added += 1
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[ok] {pool}: +{added} entries -> total {len(data['entries'])}")


if __name__ == "__main__":
    for p in POOLS:
        merge_pool(p)
