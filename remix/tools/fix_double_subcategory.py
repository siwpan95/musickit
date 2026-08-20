"""Fix entries where `file` redundantly includes the subcategory prefix
(e.g. file='bass_misc/bass (33).wav' with subcategory='bass_misc').
Strip the prefix so file is just the basename. Idempotent and safe for
acapella's legitimately nested paths (norm_rel still resolves correctly)."""
import os, json
ROOT = r"G:\music\musickit"
POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx", "keys"]
fixed = 0
for p in POOLS:
    mp = os.path.join(ROOT, p, "manifest.json")
    if not os.path.exists(mp):
        continue
    d = json.load(open(mp, encoding="utf-8"))
    for e in d.get("entries", []):
        sub = e.get("subcategory")
        f = e.get("file", "")
        if sub and isinstance(f, str) and f.startswith(sub + "/"):
            e["file"] = f[len(sub) + 1:]
            fixed += 1
    json.dump(d, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"stripped redundant prefix from {fixed} entries")
