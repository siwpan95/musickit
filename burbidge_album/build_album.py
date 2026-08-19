#!/usr/bin/env python3
# build_album.py - Assemble six instrumental tracks from G:/music/musickit stems and mix
# each of them through MULTIPLE "mix engineer" style profiles. Same stems, same
# arrangement, different console/EQ/compression/reverb/width philosophy per mixer,
# so the styles are directly A/B-comparable.
# Usage: python build_album.py            -> renders every style
#        python build_album.py ghenea     -> renders only that style slug
import os, sys, json, random, hashlib, numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsp

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = json.load(open(os.path.join(HERE, "index.json")))
INDEX = IDX["index"]
SR = dsp.SR
OUTDIR = os.path.join(HERE, "album")
CACHE = os.path.join(HERE, "_stretch_cache")
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(CACHE, exist_ok=True)
random.seed(20260818)

def key_root(k):
    if not k: return None
    return k[0] + (k[1] if len(k) > 1 and k[1] in "#b" else "")

# ---------------- selection (unchanged from the original build) ----------------
_used_paths = set()
def pick(role, tempo, kroot=None, prefer_keys=True, max_ratio=1.18,
         avoid_sub=(), prefer_sub=(), avoid_name=(), prefer_has_key=False):
    cands = [x for x in INDEX if x["cat"] == role and x["ext"] == ".wav" and x["path"] not in _used_paths]
    if not cands:
        return None
    def sub_ok(x):
        s = (x.get("subcat") or "").lower()
        return not any(b in s for b in avoid_sub)
    filtered = [x for x in cands if sub_ok(x)]
    if filtered:
        cands = filtered
    if avoid_name:
        def name_ok(x):
            n = os.path.basename(x["path"]).lower()
            return not any(b in n for b in avoid_name)
        filtered = [x for x in cands if name_ok(x)]
        if filtered:
            cands = filtered
    if kroot and prefer_keys:
        kc = [x for x in cands if key_root(x["key"]) == kroot]
        if kc: cands = kc
    if role in ("drum","bass","guita","keys","synth"):
        cands = [x for x in cands if x["bpm"]] or cands
    def score(x):
        s = (x.get("subcat") or "").lower()
        pref = 0 if any(p in s for p in prefer_sub) else 1
        haskey = 0 if (x.get("key") and key_root(x["key"])) else 1
        return (pref, haskey if prefer_has_key else 0, abs((x["bpm"] or tempo) - tempo))
    cands.sort(key=score)
    best = cands[:max(1, min(6, len(cands)))]
    chosen = random.choice(best)
    _used_paths.add(chosen["path"])
    return chosen

def pick_sfx():
    cands = [x for x in INDEX if x["cat"] == "sfx" and x["ext"] == ".wav" and x["path"] not in _used_paths]
    if not cands: return None
    hint = [x for x in cands if any(w in x["path"].lower() for w in ("transition","riser","rise","sweep","intro","impact","whoosh"))]
    chosen = random.choice(hint) if hint else random.choice(cands)
    _used_paths.add(chosen["path"])
    return chosen

def select_stems(spec):
    tempo = spec["tempo"]; kroot = spec["key"]
    PERC = ("kick","snare","hat","clap","perc","tom ","toms","cymbal","ride","rim",
            "shaker","conga","bongo","riser","impact","sweep","noise","thud","hit ","boom",
            "sfx","drum","drums","build","fill","roll","soar")
    drum = pick("drum", tempo, kroot,
                avoid_sub=("sfx","bass","sub_bass"),
                prefer_sub=("beat","drums","loop","kit"))
    bass = pick("bass", tempo, kroot,
                avoid_sub=("hat","perc","sfx","lead","guitar"),
                avoid_name=PERC,
                prefer_sub=("bass","sub"))
    pad_role = random.choice(["keys","keys","synth"])
    pad = pick(pad_role, tempo, kroot,
               avoid_sub=("drum","hat","perc","sfx","bass","sub_bass","brass"),
               avoid_name=PERC, prefer_has_key=True,
               prefer_sub=("piano","keys","pad","chord","guitar","synth","string","pluck"))
    lead_role = random.choice(["synth","guita","keys"])
    lead = pick(lead_role, tempo, kroot,
                avoid_sub=("drum","hat","perc","bass","sub_bass","sfx"),
                avoid_name=PERC, prefer_has_key=True,
                prefer_sub=("lead","melody","pluck","guitar","synth","keys"))
    bg_role = random.choice(["strings","brass","woodwind"])
    bg = pick(bg_role, tempo, kroot,
              avoid_sub=("drum","hat","perc","bass","sub_bass","sfx"),
              avoid_name=PERC, prefer_has_key=True,
              prefer_sub=("string","bowed","brass","wood","reed","flute","cello","violin"))
    sfx = pick_sfx()
    def info(r, label):
        if r: print(f"  {label:6s}: {os.path.basename(r['path'])}  bpm={r['bpm']} key={r['key']}")
        else: print(f"  {label:6s}: (none)")
    info(drum,"drum"); info(bass,"bass"); info(pad,"pad"); info(lead,"lead"); info(bg,"bg"); info(sfx,"sfx")
    return dict(drum=drum, bass=bass, pad=pad, lead=lead, bg=bg, sfx=sfx)

# ---------------- helpers ----------------
def load_stretch(rec, tempo):
    x = dsp.load_audio(rec["path"], SR)
    if rec["bpm"]:
        ratio = rec["bpm"] / tempo
        ratio = min(max(ratio, 1/1.5), 1.5)
        x = dsp.time_stretch(x, ratio, SR)
    return x

def cached_stretch(rec, tempo):
    """Stretching depends only on (stem, tempo), not on the mix style -> cache on disk."""
    if not rec["bpm"]:
        return load_stretch(rec, tempo)
    key = hashlib.sha1(f"{rec['path']}|{rec['bpm']}|{tempo}|{SR}".encode("utf-8")).hexdigest()
    fn = os.path.join(CACHE, key + ".npy")
    if os.path.exists(fn):
        return np.load(fn)
    x = load_stretch(rec, tempo)
    np.save(fn, x)
    return x

def tile(x, total):
    if len(x) >= total: return x[:total]
    out = np.zeros((total, 2), np.float32)
    pos = 0
    L = len(x)
    while pos < total:
        end = min(pos+L, total)
        out[pos:end] += x[:end-pos]
        pos += L
    return out

def add(buf, sig, start, level=1.0, width=None, pan=None):
    s = int(start)
    if s >= len(buf): return
    seg = sig[:len(buf)-s]
    seg = seg * level
    if pan is not None: seg = dsp.pan(seg, pan)
    if width is not None: seg = dsp.mid_side_widen(seg, width)
    buf[s:s+len(seg)] += seg

def prepare_audio(recs, tempo, total):
    D = tile(cached_stretch(recs["drum"], tempo), total) if recs["drum"] else np.zeros((total,2),np.float32)
    B = tile(cached_stretch(recs["bass"], tempo), total) if recs["bass"] else np.zeros((total,2),np.float32)
    P = tile(cached_stretch(recs["pad"], tempo), total) if recs["pad"] else np.zeros((total,2),np.float32)
    Ld = tile(cached_stretch(recs["lead"], tempo), total) if recs["lead"] else np.zeros((total,2),np.float32)
    BG = tile(cached_stretch(recs["bg"], tempo), total) if recs["bg"] else np.zeros((total,2),np.float32)
    SX = dsp.load_audio(recs["sfx"]["path"], SR) if recs["sfx"] else None
    return dict(D=D, B=B, P=P, Ld=Ld, BG=BG, SX=SX)

# style registry + chain renderers live in the shared mixer_styles module
# (also consumed by the random remix pipeline: remix/main.py --mixer-style)
from mixer_styles import STYLES, bus_chain, master_chain, style_irs, fmt_bus, fmt_master

# ---------------- per-style render ----------------
def render_style(spec, audio, style, irs):
    total = audio["total"]
    D, B, P, Ld, BG, SX = audio["D"], audio["B"], audio["P"], audio["Ld"], audio["BG"], audio["SX"]
    s = lambda sec: int(sec*SR)
    dbus = bus_chain(D, style["drums"], irs)
    bbus = bus_chain(B, style["bass"], irs)
    hbus = bus_chain(P, style["pad"], irs)
    lbus = bus_chain(Ld, style["lead"], irs)
    gbus = bus_chain(BG, style["bg"], irs)
    # ---- ARRANGEMENT: identical across styles (fair A/B comparison) ----
    mix = np.zeros((total,2), np.float32)
    add(mix, dbus, 0)
    add(mix, bbus, s(2.0))
    add(mix, hbus, s(1.0))
    add(mix, lbus, s(28.0))
    add(mix, lbus, s(70.0))
    add(mix, gbus, s(45.0))
    if SX is not None:
        add(mix, dsp.normalize_peak(SX, -10), s(0.0), level=0.6)
        add(mix, dsp.normalize_peak(SX, -10), s(66.0), level=0.7)
        add(mix, dsp.normalize_peak(SX, -12), s(max(0,total/SR-5.0)), level=0.5)
    sweep = np.ones(total)
    op = s(4.0)
    env = np.linspace(0,1,op)
    sweep[:op] = env
    mix[:op] *= sweep[:op,None]
    fin = s(1.0); fout = s(3.0)
    mix[:fin] *= np.linspace(0,1,fin,None)[:,None]
    mix[-fout:] *= np.linspace(1,0,fout,None)[:,None]
    # ---- master ----
    master, lufs = master_chain(mix, style["master"])
    folder = os.path.join(OUTDIR, style["folder"])
    os.makedirs(folder, exist_ok=True)
    outpath = os.path.join(folder, f"{spec['num']:02d} {spec['title']}.wav")
    sf.write(outpath, master, SR)
    return {"num": spec["num"], "title": spec["title"], "tempo": spec["tempo"],
            "key": spec["key"], "dur": float(round(total/SR,1)),
            "lufs": float(round(float(lufs),1)),
            "out": os.path.relpath(outpath, OUTDIR)}

# ---------------- album definition ----------------
TRACKS = [
    {"num":1,"title":"Midnight Velvet","tempo":88,"key":"B","bars":56},
    {"num":2,"title":"Slow Car","tempo":90,"key":"D","bars":56},
    {"num":3,"title":"Neon Rain","tempo":100,"key":"E","bars":60},
    {"num":4,"title":"Gravity","tempo":105,"key":"A","bars":60},
    {"num":5,"title":"Sunset Boulevard","tempo":110,"key":"A","bars":60},
    {"num":6,"title":"After Hours","tempo":120,"key":"C","bars":64},
]

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    styles = [st for st in STYLES if only is None or st["slug"] == only]
    if not styles:
        print("unknown style:", only); sys.exit(1)
    manifest = [dict(slug=st["slug"], name=st["name"], zh=st["zh"], folder=st["folder"],
                     color=st["color"], tagline=st["tagline"], about=st["about"],
                     refs=st["refs"], sig=st["sig"], target_lufs=st["target_lufs"],
                     impl=dict(drums=fmt_bus(st["drums"]), bass=fmt_bus(st["bass"]),
                               pad=fmt_bus(st["pad"]), lead=fmt_bus(st["lead"]),
                               bg=fmt_bus(st["bg"]), master=fmt_master(st["master"])),
                     tracks=[]) for st in styles]
    for t in TRACKS:
        print(f"\n=== Track {t['num']:02d} {t['title']}  ({t['tempo']} BPM, key {t['key']}, {t['bars']} bars) ===")
        recs = select_stems(t)
        total = int(t["bars"]*(60.0/t["tempo"])*4*SR)
        audio = prepare_audio(recs, t["tempo"], total)
        audio["total"] = total
        stem_names = {k: (os.path.basename(v["path"]) if v else None) for k, v in recs.items()}
        for st, m in zip(styles, manifest):
            irs = style_irs(st["reverb"])
            entry = render_style(t, audio, st, irs)
            entry["stems"] = stem_names
            m["tracks"].append(entry)
            print(f"  [{st['slug']:>12s}] {entry['dur']:6.1f}s  estLUFS={entry['lufs']:6.1f}  -> {entry['out']}")
    json.dump({"styles": manifest}, open(os.path.join(OUTDIR, "styles_manifest.json"), "w"),
              ensure_ascii=False, indent=2)
    # backward-compat: album_manifest.json keeps the Burbidge entries (old format)
    burb = next((m for m in manifest if m["slug"] == "burbidge"), None)
    if burb:
        json.dump(burb["tracks"], open(os.path.join(OUTDIR, "album_manifest.json"), "w"),
                  ensure_ascii=False, indent=2)
    print(f"\nDone. {len(styles)} style(s) x {len(TRACKS)} tracks rendered to", OUTDIR)
