"""Dry-run harvester: scan on-disk packs for missing musickit taxonomy classes.

Prints candidate (src_path -> target_pool/target_sub) mappings grouped by class,
WITHOUT copying. Review output, then flip DO_COPY to actually harvest.

Target classes (currently missing / thin in musickit):
  strings (entirely missing), keys/organ+accordion+harp,
  woodwind (flute/sax/clarinet/oboe), ethnic (world instruments).
Brass is intentionally crawler-only (no clean brass-wind material on disk).
"""
import os, re, sys, shutil
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

ROOTS = [os.environ.get("BAIDU_DOWNLOAD_ROOT", ""), str(_MK_ROOT.parent / "sfx-download" / "sounds")]   # 2026-09-23 去本地化
EXCLUDE_DIRS = {"output"}  # user's own remix renders -> avoid circular ingestion
AEXT = (".wav", ".mp3", ".flac", ".ogg")
DO_COPY = True  # execute the harvest

# (pool, sub, regex) -- matched against normalized text (underscores/hyphens->spaces)
RULES = [
    ("strings", "bowed", re.compile(r"violin|viola|cello|double bass|contrabass|string (ens|section|quartet|orch)")),
    ("keys", "organ", re.compile(r"(?=.*organ)(?!.*organic)")),
    ("keys", "accordion", re.compile(r"accordion|accordeon")),
    ("keys", "harp", re.compile(r"\bharp\b|harpsichord")),
    ("woodwind", "flute", re.compile(r"\bflute\b|flauta")),
    ("woodwind", "saxophone", re.compile(r"\bsax\b|saxophone|saxo\b")),
    ("woodwind", "clarinet", re.compile(r"clarinet")),
    ("woodwind", "oboe", re.compile(r"\boboe\b")),
    ("ethnic", "ethnic_world", re.compile(r"singing bowl|\btabla\b|\bdjembe\b|\bgong\b|\bkoto\b|\bsitar\b|\berhu\b|\bguzheng\b|china drum|\btaiko\b|shakuhachi|didgeridoo|\bkalimba\b|pan flute|\braga\b|santoor|balalaika|\boud\b|bouzouki|charango")),
]

MUSICKIT = str(_MK_ROOT)


def classify(norm):
    # synth-role patches belong in the (already populated) synth pool, not here
    if "synth" in norm:
        return None
    for pool, sub, rx in RULES:
        if rx.search(norm):
            return pool, sub
    return None


def main():
    hits = {}
    files_seen = 0
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, dirs, names in os.walk(root):
            # prune excluded dirs in-place
            dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_DIRS]
            for n in names:
                if not n.lower().endswith(AEXT):
                    continue
                files_seen += 1
                norm = re.sub(r"[\W_]+", " ", (n + " " + dirpath).lower())
                m = classify(norm)
                if m:
                    hits.setdefault(m, []).append(os.path.join(dirpath, n))
    print(f"Scanned {files_seen} audio files across {len(ROOTS)} roots (output/ excluded).")
    total = 0
    for (pool, sub), paths in sorted(hits.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        print(f"\n### {pool}/{sub}  ({len(paths)} candidates)")
        for p in paths:
            print("   ", p)
        total += len(paths)
    print(f"\nTOTAL candidates: {total}")

    if DO_COPY:
        print("\n=== COPYING ===")
        for (pool, sub), paths in hits.items():
            dst_root = os.path.join(MUSICKIT, pool, sub)
            os.makedirs(dst_root, exist_ok=True)
            for p in paths:
                base = os.path.basename(p)
                dest = os.path.join(dst_root, base)
                i = 1
                while os.path.exists(dest):
                    stem, ext = os.path.splitext(base)
                    dest = os.path.join(dst_root, f"{stem}_{i}{ext}")
                    i += 1
                shutil.copy2(p, dest)
            print(f"copied {len(paths)} -> {dst_root}")


if __name__ == "__main__":
    main()
