"""Generic manifest-to-disk sync for ALL musickit pools.

For each pool in CATEGORIES: load its manifest.json {"entries":[...]} (or start
empty), walk the pool directory, and append a manifest entry for every audio file
on disk whose basename is not already represented. Entry shape matches the
subdivide convention: {file: <basename>, subcategory: <subfolder or '(root)'>}.

Run this after any bulk file addition (harvest or crawler ingest) so the
per-pool manifests stay consistent with disk before rebuilding manifest_index.
"""
import json, os

MUSICKIT = r"G:\music\musickit"
POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
         "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")


def sync_pool(pool):
    pool_dir = os.path.join(MUSICKIT, pool)
    if not os.path.isdir(pool_dir):
        return
    mp = os.path.join(pool_dir, "manifest.json")
    if os.path.exists(mp):
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "entries" not in data:
            data = {"generated_by": "sync_manifests_to_disk", "entries": []}
    else:
        data = {"generated_by": "sync_manifests_to_disk", "entries": []}

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
                "source_pack": "sync",
                "original": n,
                "original_rel": sub,
                "license": "see source",
                "duration_s": None,
            })
            existing.add(n)
            added += 1
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    if added:
        print(f"[ok] {pool}: +{added} -> total {len(data['entries'])}")


if __name__ == "__main__":
    for p in POOLS:
        sync_pool(p)
    print("sync complete")
