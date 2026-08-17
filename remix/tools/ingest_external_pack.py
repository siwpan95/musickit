"""Ingest external sample packs (dirs, .zip, or dirs containing .zip) into musickit pools.

Classifies each audio file by PARENT FOLDER name first, then by filename
keywords. Routes only into gap-relevant pools {strings, brass, woodwind,
ethnic, keys, guita}; drum/bass/sfx/vocal are deliberately NOT mapped, so they
are skipped (those pools are already ample). Nested .zip files inside a source
directory are also processed.

Files are copied into G:\\musickit\\<pool>\\<instrument>\\ . Per-pool manifests
are NOT written here -- run sync_manifests_to_disk.py afterwards.

Usage:
    ingest_external_pack.py --dry-run <src> [<src2> ...]
    ingest_external_pack.py <src> [<src2> ...]
"""
import os, sys, shutil, argparse, zipfile

MUSICKIT = r"G:\musickit"
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")
AEXT_NODOT = tuple(e[1:] for e in AEXT)
TARGET_POOLS = {"strings", "brass", "woodwind", "ethnic", "keys", "guita"}

# (keyword, pool, instrument) -- ORDER MATTERS (specific before generic).
KEYWORDS = [
    ("doublebass", "strings", "doublebass"),
    ("double bass", "strings", "doublebass"),
    ("contrabass", "strings", "contrabass"),
    ("violin", "strings", "violin"),
    ("viola", "strings", "viola"),
    ("cello", "strings", "cello"),
    ("violoncello", "strings", "cello"),
    ("string", "strings", "strings"),
    ("frenchhorn", "brass", "frenchhorn"),
    ("french horn", "brass", "frenchhorn"),
    ("trumpet", "brass", "trumpet"),
    ("trombone", "brass", "trombone"),
    ("tuba", "brass", "tuba"),
    ("cornet", "brass", "cornet"),
    ("flugel", "brass", "flugelhorn"),
    ("saxophone", "brass", "saxophone"),
    ("sax", "brass", "saxophone"),
    ("englishhorn", "woodwind", "english_horn"),
    ("english horn", "woodwind", "english_horn"),
    ("horn", "brass", "horn"),
    ("clarinet", "woodwind", "clarinet"),
    ("oboe", "woodwind", "oboe"),
    ("flute", "woodwind", "flute"),
    ("bassoon", "woodwind", "bassoon"),
    ("piccolo", "woodwind", "piccolo"),
    ("recorder", "woodwind", "recorder"),
    ("woodwind", "woodwind", "woodwind"),
    ("sitar", "ethnic", "sitar"),
    ("tabla", "ethnic", "tabla"),
    ("erhu", "ethnic", "erhu"),
    ("guzheng", "ethnic", "guzheng"),
    ("koto", "ethnic", "koto"),
    ("taiko", "ethnic", "taiko"),
    ("dhol", "ethnic", "dhol"),
    ("bansuri", "ethnic", "bansuri"),
    ("ethnic", "ethnic", "ethnic"),
    ("celesta", "keys", "celesta"),
    ("rhodes", "keys", "rhodes"),
    ("organ", "keys", "organ"),
    ("accordion", "keys", "accordion"),
    ("harp", "keys", "harp"),
    ("epiano", "keys", "rhodes"),
    ("piano", "keys", "piano"),
    ("key", "keys", "keys"),
    ("synthesizer", "synth", "synth"),
    ("synth", "synth", "synth"),
    ("syn pad", "synth", "pad"),
    ("pad", "synth", "pad"),
    ("guitar", "guita", "guitar"),
    ("acapella", "acapella", "acapella"),
    ("a cappella", "acapella", "acapella"),
    ("vocal", "acapella", "vocal"),
    ("voice", "acapella", "vocal"),
]


def norm(s):
    return "".join(c if c.isalnum() else " " for c in s.lower())


def classify(folder_hint, filename):
    parts = [p for p in folder_hint.replace("\\", "/").split("/") if p]
    probe = norm(filename)
    if parts:
        probe = norm(parts[-1]) + " " + probe
    full = norm(folder_hint) + " " + norm(filename)
    for kw, pool, instr in KEYWORDS:
        if kw in probe or kw in full:
            return pool, instr
    return None


def _unique_dst(dst):
    if not os.path.exists(dst):
        return dst
    base, ext = os.path.splitext(dst)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def ingest_zip(src, args, tally, counters):
    try:
        zf = zipfile.ZipFile(src)
    except Exception as e:
        print(f"  [zip-open-fail] {os.path.basename(src)}: {e}")
        return
    with zf:
        members = [i for i in zf.infolist()
                   if i.filename.lower().rsplit(".", 1)[-1] in AEXT_NODOT]
        for m in members:
            name = m.filename
            base = os.path.basename(name)
            folder = os.path.dirname(name)
            res = classify(folder, base)
            if not res:
                counters["skipped"] += 1
                continue
            pool, instr = res
            dst = _unique_dst(os.path.join(MUSICKIT, pool, instr, base))
            if not args.dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(m) as f, open(dst, "wb") as out:
                    shutil.copyfileobj(f, out)
                counters["copied"] += 1
            tally[(pool, instr)] = tally.get((pool, instr), 0) + 1


def ingest_dir(src, args, tally, counters):
    for r, _, files in os.walk(src):
        # nested zips first
        for f in files:
            if f.lower().endswith(".zip"):
                ingest_zip(os.path.join(r, f), args, tally, counters)
        for f in files:
            if f.lower().rsplit(".", 1)[-1] not in AEXT_NODOT:
                continue
            res = classify(r, f)
            if not res:
                counters["skipped"] += 1
                continue
            pool, instr = res
            dst = _unique_dst(os.path.join(MUSICKIT, pool, instr, f))
            if not args.dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(r, f), dst)
                counters["copied"] += 1
            tally[(pool, instr)] = tally.get((pool, instr), 0) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="dirs or .zip archives")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tally = {}
    counters = {"copied": 0, "skipped": 0}
    for src in args.sources:
        if not os.path.exists(src):
            print("MISSING:", src)
            continue
        if src.lower().endswith(".zip"):
            ingest_zip(src, args, tally, counters)
        else:
            ingest_dir(src, args, tally, counters)

    print(f"\n=== {'DRY-RUN ' if args.dry_run else ''}SUMMARY ===")
    print(f"copied={counters['copied']} skipped(non-gap)={counters['skipped']}")
    for (pool, instr), c in sorted(tally.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f"  {pool:9s}/{instr:12s} {c}")
    if not args.dry_run:
        print("\nNext: run sync_manifests_to_disk.py then build_manifest_index.py")


if __name__ == "__main__":
    main()
