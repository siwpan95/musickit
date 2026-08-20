import os, json
ROOT = r"G:\music\musickit"
POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx"]
AEXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
for p in POOLS:
    mp = os.path.join(ROOT, p, "manifest.json")
    info = "MISSING"
    if os.path.exists(mp):
        try:
            d = json.load(open(mp, encoding="utf-8"))
            ents = d.get("entries", [])
            info = f"{len(ents)} entries, keys={list(d.keys())[:3]}, has_subcat={any('subcategory' in e for e in ents)}"
        except Exception as ex:
            info = f"ERR {ex!r}"
    root_flat = []
    subs = {}
    pdir = os.path.join(ROOT, p)
    for name in sorted(os.listdir(pdir)):
        fp = os.path.join(pdir, name)
        if os.path.isdir(fp):
            c = sum(1 for f in os.listdir(fp) if f.lower().endswith(AEXT))
            subs[name] = c
        elif name.lower().endswith(AEXT):
            root_flat.append(name)
    print(f"== {p} ==")
    print(f"  manifest: {info}")
    print(f"  root flat: {len(root_flat)} | subfolders: {subs}")
    sub_files = set()
    for s in subs:
        sd = os.path.join(pdir, s)
        for f in os.listdir(sd):
            if f.lower().endswith(AEXT):
                sub_files.add(f.lower())
    dup = [f for f in root_flat if f.lower() in sub_files]
    if dup:
        print(f"  >>> DUPLICATES(root+sub) count={len(dup)} e.g. {dup[:3]}")
print("\n--- drum (150).wav specific ---")
for loc in [r"G:\music\musickit\drum\drum (150).wav", r"G:\music\musickit\drum\drum_misc\drum (150).wav"]:
    print(f"  {'EXISTS' if os.path.exists(loc) else 'absent '}: {loc}")
