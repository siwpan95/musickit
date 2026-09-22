"""verify_release_fidelity.py — 用**内容比对**证明重渲产物 == 原产物。

为什么不能靠文件名
------------------
`output/hourly/` 下的历史 mp3 被外部进程批量改名并移入子目录
（`loop/loop (N).mp3`、`ambient/ambient (N).mp3`、`.archived/`），
索引里的 `path` 早已失效，**按文件名找不到原文件**。
因此改用内容比对：把两份音频都解码成 8 kHz 单声道，取 10 ms 窗 RMS 包络，
算 Pearson 相关系数 r —— 同一编排应接近 1.0，不同内容会明显偏低。

附加判据（比"能匹配上"更强）
-------------------------
* **双向唯一（bijection）**：每首重渲 wav 的最佳匹配应互不重复，
  且候选池里每个原文件最多被一首匹配 —— 排除"都匹配到同一首"的假阳性。
* 报告 r 的分布（min / 中位 / 均值），阈值 `--min-r`（默认 0.99）。

用法
----
    F:\\Python314\\python.exe tools\\verify_release_fidelity.py            # 全量核验
    F:\\Python314\\python.exe tools\\verify_release_fidelity.py --min-r 0.98
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(REMIX_DIR, "output", "hourly")
DEFAULT_REL = os.path.join(REMIX_DIR, "output", "release")

# 本目录加入 sys.path（本机设了 PYTHONSAFEPATH=1，脚本目录不会自动加入）
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import audio_fingerprint as AF  # noqa: E402

ENVELOPE_SR = AF.ENVELOPE_SR


def envelope(path: str):
    return AF.envelope(path, sr=ENVELOPE_SR)


def corr(a, b):
    return AF.envelope_corr(a, b)


def collect_candidates(root: str) -> list[str]:
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".mp3", ".wav", ".flac")):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="内容比对核验重渲保真度")
    ap.add_argument("--release-dir", default=DEFAULT_REL)
    ap.add_argument("--source-dir", default=DEFAULT_SRC, help="原产物所在树（会递归扫描）")
    ap.add_argument("--min-r", type=float, default=0.99)
    ap.add_argument("--patch-index", action="store_true",
                    help="把比对结果写回 release_index.json 的 fidelity_match 字段")
    args = ap.parse_args()

    rel_index = os.path.join(args.release_dir, "release_index.json")
    with open(rel_index, "r", encoding="utf-8") as fh:
        rel = json.load(fh)

    cands = collect_candidates(args.source_dir)
    rel_files = [os.path.join(args.release_dir, e["file"]) for e in rel]
    print(f"重渲产物 {len(rel_files)} 首 | 候选原文件 {len(cands)} 个（递归 {args.source_dir}）")

    print("解码候选原文件包络…", flush=True)
    cand_env = {p: envelope(p) for p in cands}
    cand_env = {p: v for p, v in cand_env.items() if v is not None}

    rows, claimed = [], {}
    for e, path in zip(rel, rel_files):
        env = envelope(path)
        best_p, best_r = None, -1.0
        for cp, ce in cand_env.items():
            r = corr(env, ce)
            if r is not None and r > best_r:
                best_p, best_r = cp, r
        claimed.setdefault(best_p, []).append(e["file"])
        rows.append({
            "file": e["file"], "best_match": os.path.relpath(best_p, args.source_dir) if best_p else None,
            "r": None if best_r < 0 else round(best_r, 5),
            "pass": bool(best_r >= args.min_r),
        })

    rs = [x["r"] for x in rows if x["r"] is not None]
    rs_sorted = sorted(rs)
    n_pass = sum(1 for x in rows if x["pass"])
    dup = {k: v for k, v in claimed.items() if len(v) > 1}

    print()
    print("=" * 78)
    print(f"阈值 min-r = {args.min_r}")
    print(f"通过 {n_pass}/{len(rows)}  （r 中位 {rs_sorted[len(rs_sorted)//2]:.5f} / "
          f"最小 {rs_sorted[0]:.5f} / 均值 {sum(rs)/len(rs):.5f}）" if rs else "无有效比对")
    print(f"双向唯一性：{len(rows) - len(dup)}/{len(rows)} 首匹配到互不重复的候选"
          f"{'（存在复用：' + str(list(dup.values())) + '）' if dup else ''}")
    print("=" * 78)
    print(f"{'重渲产物':<62} {'最佳匹配原文件':<34} {'r':>8}")
    for x in sorted(rows, key=lambda y: (y["r"] is None, y["r"] or 0)):
        flag = "OK " if x["pass"] else "LOW"
        rtxt = "-" if x["r"] is None else format(x["r"], ".5f")
        print(f"{flag} {x['file'][:60]:<60} {(x['best_match'] or '-'):<34} {rtxt:>8}")

    if args.patch_index:
        by_file = {x["file"]: x for x in rows}
        for e in rel:
            m = by_file.get(e["file"])
            if m:
                e["fidelity_match"] = {"best_match": m["best_match"], "r": m["r"],
                                       "pass": m["pass"], "min_r": args.min_r}
                e["fidelity_corr"] = m["r"]
                e["reproduced"] = bool(m["pass"])
        tmp = rel_index + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rel, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, rel_index)
        print(f"\n已回写核验结果 → {rel_index}")

    return 0 if n_pass == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
