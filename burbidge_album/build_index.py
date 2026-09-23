#!/usr/bin/env python3
# Build a real-file index of the musickit repo by scanning the ACTUAL tree,
# and recover BPM/key/subcategory for each file via manifest_index.json (matched by filename).
import os, re, json, collections
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[1])   # 2026-09-23 去本地化
BASE = str(_MK_ROOT)
MANIFEST = os.path.join(BASE, "manifest_index.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.json")

# Only consider these musical roles (exclude fix/trash/meta dirs and the copyrighted acapella set)
ROLES = ["drum","bass","guita","keys","synth","strings","brass","woodwind","ethnic","sfx","cowbell"]
EXCLUDE_DIRS = {".git",".subdivide_trash",".workbuddy","archived","music","remix",
                "musickit-fix-20260817","acapella","animal"}

bpm_pat = re.compile(r'(\d{2,3})\s*(?:bpm|BPM)')
bpm_standalone = re.compile(r'(?<![0-9])(7[0-9]|8[0-9]|9[0-9]|1[0-3][0-9]|14[0-9]|1[5-9][0-9]|200)(?![0-9])')
key_pat = re.compile(r'(?<![A-Za-z])([A-G][#b]?)((?:maj|min|m|M|sus|dim|add|aug|7|9|11|13)*)')

def parse_bpm(text):
    m = bpm_pat.search(text)
    if m:
        v = int(m.group(1))
        if 60 <= v <= 200:
            return v
    m = bpm_standalone.search(text)
    if m:
        v = int(m.group(1))
        if 60 <= v <= 200:
            return v
    return None

def parse_key(text):
    # find the most plausible note token; prefer one followed by a scale qualifier
    best = None
    for m in key_pat.finditer(text):
        note, qual = m.group(1), m.group(2)
        if qual:
            return note + qual  # e.g. Am, Cmaj
        best = note
    return best

# Load manifest, build (cat -> file -> entry)
manifest = json.load(open(MANIFEST))
mcat = {}
for cat, c in manifest["categories"].items():
    d = {}
    for e in c.get("entries", []):
        d[e["file"]] = e
    mcat[cat] = d

index = []
counts = collections.Counter()
for root, dirs, files in os.walk(BASE):
    # prune excluded top-level dirs
    parts = os.path.relpath(root, BASE).split(os.sep)
    top = parts[0] if parts[0] != "." else ""
    if top in EXCLUDE_DIRS:
        dirs[:] = []
        continue
    if top not in ROLES:
        # still recurse but don't collect (e.g. nested unknown)
        pass
    for fn in files:
        if not fn.lower().endswith((".wav",".mp3")):
            continue
        if fn.startswith("._") or fn in (".DS_Store",):
            continue
        cat = top
        if cat not in ROLES:
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, BASE)
        entry = mcat.get(cat, {}).get(fn)
        bpm = None; subcat = None; pack = None
        if entry:
            bpm = parse_bpm(entry.get("original_rel","") or entry.get("original",""))
            subcat = entry.get("subcategory")
            pack = entry.get("source_pack")
        if bpm is None:
            bpm = parse_bpm(rel)
        if subcat is None:
            subcat = "(root)"
        # key from filename (basename without ext) + parent folder
        key = parse_key(os.path.splitext(fn)[0]) or parse_key(os.path.basename(os.path.dirname(full)))
        rec = {
            "path": full, "cat": cat, "bpm": bpm, "key": key,
            "subcat": subcat, "pack": pack, "ext": os.path.splitext(fn)[1].lower(),
        }
        index.append(rec)
        counts[cat] += 1

print("Indexed files:", len(index))
for c, n in counts.most_common():
    print(f"  {c:10s} {n}")

# Feasibility: for candidate tempos, count exact-BPM stems per role (real files, non-mp3 from acapella excluded already)
TEMPOS = [80,85,88,90,94,95,100,105,110,115,120,125,128,130]
KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def key_root(k):
    if not k: return None
    return k[0] + (k[1] if len(k)>1 and k[1] in "#b" else "")

print("\n=== Per-tempo role pools (exact BPM, real files) ===")
print("TEMPO | " + " ".join(f"{r[:4]}" for r in ["drum","bass","guita","keys","synth","strings","brass","woodwind"]))
roles = ["drum","bass","guita","keys","synth","strings","brass","woodwind"]
for t in TEMPOS:
    row=[]
    for r in roles:
        n=sum(1 for x in index if x["cat"]==r and x["bpm"]==t and x["ext"]==".wav")
        row.append(f"{n:4d}")
    print(f"  {t:3d} | " + " ".join(row))

# key availability at 90/100/105/110
print("\n=== Key availability at core tempos (harmonic roles: keys/guita/synth/strings/brass) ===")
for t in [90,100,105,110]:
    kc=collections.Counter()
    for x in index:
        if x["cat"] in ("keys","guita","synth","strings","brass") and x["bpm"]==t and x["ext"]==".wav" and x["key"]:
            kc[key_root(x["key"])]+=1
    print(f"  {t} BPM keys:", dict(kc))

json.dump({"base":BASE,"index":index}, open(OUT,"w"), ensure_ascii=False)
print("\nWrote", OUT)
