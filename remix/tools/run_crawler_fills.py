"""Driver: fetch missing taxonomy classes via the sfx crawler, then route + sync.

Runs dl_keyword.py (Playwright) for each "keyword:count" target using the
crawler venv Python, then runs ingest_crawler_output.py + sync_manifests_to_disk.py
to land the downloads into musickit pools and reconcile manifests.

Usage:
    run_crawler_fills.py                 # use DEFAULT_TARGETS
    run_crawler_fills.py violin:5 cello:5   # explicit smoke-test set
"""
import os, subprocess, sys

SFX = r"G:\tools\sfx"
# venv pip-seeding was broken in this sandbox; use the managed base python
# (an isolated runtime) which now has playwright + chromium installed.
VENV_PY = r"C:\Users\13122\.workbuddy\binaries\python\versions\3.13.12\python.exe"
MUSICKIT = r"G:\music\musickit"

# (keyword, count) — the taxonomy gaps not covered by on-disk harvest
DEFAULT_TARGETS = [
    ("violin", 40), ("cello", 40), ("viola", 20), ("double bass", 20),
    ("trumpet", 40), ("trombone", 30), ("french horn", 20), ("tuba", 20),
    ("clarinet", 30), ("oboe", 30),
    ("accordion", 30), ("harp", 20), ("organ", 20),
    ("flute", 20), ("saxophone", 20),
]


def main():
    args = sys.argv[1:]
    if args:
        targets = []
        for a in args:
            kw, _, n = a.partition(":")
            targets.append((kw.strip(), int(n) if n else 30))
    else:
        targets = DEFAULT_TARGETS

    if not os.path.exists(VENV_PY):
        print("venv python missing:", VENV_PY, "-> run crawler setup first")
        sys.exit(1)

    for kw, n in targets:
        print(f"\n===== crawl: {kw} (n={n}) =====")
        try:
            r = subprocess.run(
                [VENV_PY, "dl_keyword.py", kw, "-n", str(n)],
                cwd=SFX, capture_output=True, text=True, timeout=600,
            )
            print(r.stdout[-1500:] if r.stdout else "(no stdout)")
            if r.stderr:
                print("STDERR:", r.stderr[-800:])
            print(f"rc={r.returncode}")
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT on {kw}")
        except Exception as e:
            print(f"ERR {kw}: {e}")

    print("\n===== ingest crawler output into musickit =====")
    subprocess.run([VENV_PY, os.path.join(r"G:\music\musickit\remix\tools", "ingest_crawler_output.py")],
                   cwd=r"G:\music\musickit\remix\tools")
    print("\n===== sync manifests to disk =====")
    subprocess.run([VENV_PY, os.path.join(r"G:\music\musickit\remix\tools", "sync_manifests_to_disk.py")],
                   cwd=r"G:\music\musickit\remix\tools")
    print("\nALL DONE. Next: rebuild manifest_index.py (run build_manifest_index.py).")


if __name__ == "__main__":
    main()
