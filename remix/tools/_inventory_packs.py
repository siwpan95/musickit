"""Read-only inventory of G:\\BaiduNetdiskDownload: count audio files per pack.

Groups by the immediate sub-folder (already-extracted packs) or by archive
filename (still-compressed packs). For archives we read the listing only
(zipfile central directory; 7z/rar if a reader is importable) -- no extraction.
"""
import os, sys, zipfile

BASE = os.environ.get("BAIDU_DOWNLOAD_ROOT", "")   # 2026-09-23 去本地化（原百度网盘下载目录为本机专有）
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")
AEXT_NODOT = tuple(e[1:] for e in AEXT)  # ("wav","mp3",...) for extension-after-dot compare

# try optional readers
try:
    import py7zr
    HAVE_7Z = True
except Exception:
    HAVE_7Z = False
try:
    import rarfile
    HAVE_RAR = True
except Exception:
    HAVE_RAR = False


def classify_pool(name):
    n = name.lower()
    rules = [
        ("strings", ["violin", "viola", "cello", "double bass", "contrabass", "string", "orchestr", "symphon"]),
        ("brass", ["trumpet", "trombone", "horn", "tuba", "brass", "sax", "saxophone", "cornet", "flugel"]),
        ("woodwind", ["flute", "clarinet", "oboe", "bassoon", "piccolo", "recorder", "woodwind"]),
        ("ethnic", ["sitar", "tabla", "erhu", "guzheng", "koto", "taiko", "dhol", "bansuri", "ethnic", "world", "gamelan", "didgeridoo"]),
        ("keys", ["piano", "key", "organ", "accordion", "harp", "rhodes", "synth", "epad", "fender"]),
        ("guita", ["guitar", "bass guitar", "acoustic", "electric guitar"]),
        ("bass", ["bass", "sub", "808"]),
        ("drum", ["drum", "perc", "kick", "snare", "hat", "cymbal", "tom", "loop", "beat", "clap"]),
        ("acapella", ["vocal", "acapella", "a capella", "voice", "choir", "rap", "adlib"]),
        ("sfx", ["sfx", "fx", "impact", "riser", "whoosh", "zap", "noise", "foley"]),
    ]
    hits = []
    for pool, kws in rules:
        if any(k in n for k in kws):
            hits.append(pool)
    # priority order for ambiguous
    for pool in ["strings", "brass", "woodwind", "ethnic", "keys", "guita", "bass", "drum", "acapella", "sfx"]:
        if pool in hits:
            return pool
    return "other"


def count_embedded_archive(path):
    ext = path.lower().rsplit(".", 1)[-1]
    try:
        if ext == "zip":
            with zipfile.ZipFile(path) as z:
                names = [i.filename for i in z.infolist()]
        elif ext == "7z" and HAVE_7Z:
            with py7zr.SevenZipFile(path, "r") as z:
                names = z.getnames()
        elif ext == "rar" and HAVE_RAR:
            with rarfile.RarFile(path) as z:
                names = z.namelist()
        else:
            return None, []
        audio = [n for n in names if n.lower().rsplit(".", 1)[-1] in AEXT_NODOT]
        return len(audio), audio
    except Exception as e:
        return -1, [f"ERR:{e}"]


def main():
    print(f"BASE={BASE}  HAVE_7Z={HAVE_7Z} HAVE_RAR={HAVE_RAR}\n")
    rows = []  # (pack, kind, total_audio, by_pool_dict)
    for entry in sorted(os.listdir(BASE)):
        full = os.path.join(BASE, entry)
        if os.path.isdir(full):
            # already-extracted pack: walk audio
            counts = {}
            total = 0
            for r, _, files in os.walk(full):
                for f in files:
                    if f.lower().rsplit(".", 1)[-1] in AEXT_NODOT:
                        total += 1
                        p = classify_pool(os.path.join(r, f))
                        counts[p] = counts.get(p, 0) + 1
            rows.append((entry, "DIR", total, counts))
        else:
            ext = entry.lower().rsplit(".", 1)[-1]
            if ext in ("zip", "7z", "rar"):
                n, audio = count_embedded_archive(full)
                if n is None:
                    rows.append((entry, "ARCHIVE(unreadable)", 0, {}))
                elif n == -1:
                    rows.append((entry, "ARCHIVE(error)", 0, {}))
                else:
                    counts = {}
                    for a in audio:
                        p = classify_pool(a)
                        counts[p] = counts.get(p, 0) + 1
                    rows.append((entry, f"ARCHIVE({ext})", n, counts))
            # else: loose file (skip)

    # also scan subfolder 1 (free trial, mostly extracted dirs already covered by walk? no -- it's under BASE/1)
    # walk BASE/1 too:
    sub1 = os.path.join(BASE, "1")
    if os.path.isdir(sub1):
        for entry in sorted(os.listdir(sub1)):
            full = os.path.join(sub1, entry)
            if os.path.isdir(full):
                counts = {}
                total = 0
                for r, _, files in os.walk(full):
                    for f in files:
                        if f.lower().rsplit(".", 1)[-1] in AEXT_NODOT:
                            total += 1
                            p = classify_pool(os.path.join(r, f))
                            counts[p] = counts.get(p, 0) + 1
                rows.append((f"1/{entry}", "DIR", total, counts))

    # print
    pools = ["strings", "brass", "woodwind", "ethnic", "keys", "guita", "bass", "drum", "acapella", "sfx", "other"]
    for name, kind, total, counts in sorted(rows, key=lambda x: -x[2]):
        if total == 0 and kind.startswith("DIR"):
            continue
        dist = " ".join(f"{p}={counts.get(p,0)}" for p in pools if counts.get(p, 0))
        print(f"[{kind:18s}] {name}")
        print(f"    audio={total}  {dist}")


if __name__ == "__main__":
    main()
