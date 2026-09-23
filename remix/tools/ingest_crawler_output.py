"""Route crawler downloads (G:\\tools\\sfx\\sounds\\<keyword>\\*) into musickit pools.

The sfx crawler (dl_keyword.py) saves per-keyword folders under sfx/sounds/.
This script maps each folder name to a (pool, subcategory) and copies the audio
files into G:\\music\\musickit\\<pool>\\<subcategory>\\ (de-duping collisions), so the
generic sync_manifests_to_disk.py can then manifest them.

Routing is keyword-based: a folder name containing any KEYWORD map key is routed
to that key's (pool, sub). Unknown folders are reported and skipped.
"""
import os, shutil, sys
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

CRAWL_ROOT = str(_MK_ROOT.parent / "sfx-download" / "sounds")   # 2026-09-23 去本地化
MUSICKIT = str(_MK_ROOT)
AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac")

# instrument keyword -> (pool, subcategory)
KEYWORD = {
    "violin": ("strings", "bowed"),
    "viola": ("strings", "bowed"),
    "cello": ("strings", "bowed"),
    "double bass": ("strings", "bowed"),
    "contrabass": ("strings", "bowed"),
    "upright bass": ("strings", "bowed"),
    "trumpet": ("brass", "brass"),
    "trombone": ("brass", "brass"),
    "french horn": ("brass", "brass"),
    "tuba": ("brass", "brass"),
    "clarinet": ("woodwind", "clarinet"),
    "oboe": ("woodwind", "oboe"),
    "flute": ("woodwind", "flute"),
    "sax": ("woodwind", "saxophone"),
    "organ": ("keys", "organ"),
    "accordion": ("keys", "accordion"),
    "harp": ("keys", "harp"),
    # ethnic supplements
    "sitar": ("ethnic", "ethnic_world"),
    "erhu": ("ethnic", "ethnic_world"),
    "guzheng": ("ethnic", "ethnic_world"),
    "tabla": ("ethnic", "ethnic_world"),
    "taiko": ("ethnic", "ethnic_world"),
    "koto": ("ethnic", "ethnic_plucked"),
}


def route_for(folder_name):
    low = folder_name.lower()
    for k, v in KEYWORD.items():
        if k in low:
            return v
    return None


def main():
    if not os.path.isdir(CRAWL_ROOT):
        print("crawl root missing:", CRAWL_ROOT)
        sys.exit(1)
    total = 0
    unknown = []
    for name in sorted(os.listdir(CRAWL_ROOT)):
        fp = os.path.join(CRAWL_ROOT, name)
        if not os.path.isdir(fp):
            continue
        r = route_for(name)
        if not r:
            unknown.append(name)
            continue
        pool, sub = r
        dst = os.path.join(MUSICKIT, pool, sub)
        os.makedirs(dst, exist_ok=True)
        n = 0
        for fn in sorted(os.listdir(fp)):
            if not fn.lower().endswith(AEXT):
                continue
            src = os.path.join(fp, fn)
            dest = os.path.join(dst, fn)
            i = 1
            while os.path.exists(dest):
                stem, ext = os.path.splitext(fn)
                dest = os.path.join(dst, f"{stem}_{i}{ext}")
                i += 1
            shutil.copy2(src, dest)
            n += 1
        total += n
        print(f"[ok] {name} -> {pool}/{sub}  ({n} files)")
    if unknown:
        print("\n[skip] unknown folders (no keyword match):")
        for u in unknown:
            print("   ", u)
    print(f"\nTotal routed: {total}")


if __name__ == "__main__":
    main()
