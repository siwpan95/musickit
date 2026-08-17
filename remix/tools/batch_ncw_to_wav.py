#!/usr/bin/env python
"""Batch convert NCW -> WAV using the built-in numpy decoder (ncw_to_wav.py).

Usage:
    batch_ncw_to_wav.py <ncw_root | list.txt> <out_root> [--jobs N]

- Keeps the relative directory structure (instrument/articulation), which
  ingest_external_pack.py uses for pool classification (parent-dir first).
- Resumable: skips inputs whose output .wav already exists with size > 0.
- Failures are recorded in <out_root>/_failed.txt.
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ncw_to_wav import decode_ncw, write_wav  # noqa: E402


def collect(arg):
    if arg.lower().endswith(".txt"):
        with open(arg, encoding="utf-8-sig", errors="replace") as f:
            return [ln.strip().strip('"') for ln in f if ln.strip()]
    out = []
    for dp, _, fns in os.walk(arg):
        for fn in fns:
            if fn.lower().endswith(".ncw"):
                out.append(os.path.join(dp, fn))
    return out


def convert_one(job):
    src, dst = job
    try:
        if os.path.exists(dst) and os.path.getsize(dst) > 44:
            return (src, "skip")
        info = decode_ncw(src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        write_wav(dst, info)
        return (src, "ok")
    except Exception as e:
        return (src, f"fail {type(e).__name__}: {e}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src_arg, out_root = sys.argv[1], sys.argv[2]
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 8

    files = collect(src_arg)
    base = src_arg if not src_arg.lower().endswith(".txt") else os.path.commonpath(files)
    jobs_list = []
    for f in files:
        rel = os.path.relpath(f, base)
        dst = os.path.join(out_root, os.path.splitext(rel)[0] + ".wav")
        jobs_list.append((f, dst))

    print(f"inputs: {len(jobs_list)}  jobs: {jobs}  out: {out_root}", flush=True)
    ok = skip = 0
    failed = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for i, (src, status) in enumerate(ex.map(convert_one, jobs_list, chunksize=16), 1):
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                failed.append((src, status))
            if i % 200 == 0 or i == len(jobs_list):
                print(f"  [{i}/{len(jobs_list)}] ok={ok} skip={skip} fail={len(failed)}", flush=True)
    if failed:
        with open(os.path.join(out_root, "_failed.txt"), "a", encoding="utf-8") as f:
            for s, st in failed:
                f.write(f"{st}\t{s}\n")
    print(f"DONE ok={ok} skip={skip} fail={len(failed)}", flush=True)


if __name__ == "__main__":
    main()
