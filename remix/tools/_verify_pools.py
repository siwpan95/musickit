import os, json, collections
BASE = r"G:\music\musickit"
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")
AEXT_NODOT = tuple(e[1:] for e in AEXT)
POOLS = ["bass", "drum", "guita", "cowbell", "synth", "acapella", "animal", "sfx",
         "keys", "strings", "brass", "woodwind", "ethnic"]

disk = collections.Counter()
man = collections.Counter()
for p in POOLS:
    d = os.path.join(BASE, p)
    n_disk = 0
    for r, _, files in os.walk(d):
        for f in files:
            if f.lower().rsplit(".", 1)[-1] in AEXT_NODOT:
                n_disk += 1
    disk[p] = n_disk
    mp = os.path.join(d, "manifest.json")
    n_man = 0
    if os.path.exists(mp):
        try:
            n_man = len(json.load(open(mp, encoding="utf-8")).get("entries", []))
        except Exception:
            n_man = -1
    man[p] = n_man

print(f"{'pool':10s} {'disk':>7s} {'manifest':>9s}  status")
tot_d = tot_m = 0
for p in POOLS:
    flag = "" if disk[p] == man[p] else "  <-- MISMATCH"
    print(f"{p:10s} {disk[p]:7d} {man[p]:9d}{flag}")
    tot_d += disk[p]; tot_m += man[p] if man[p] >= 0 else 0
print(f"{'TOTAL':10s} {tot_d:7d} {tot_m:9d}")
print("OK" if all(disk[p] == man[p] for p in POOLS) else "HAS MISMATCH")
