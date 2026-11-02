"""doctor — musickit 环境与素材一致性自检（T0-2）。

为什么需要它：
  仓库把「素材音频」和「ffmpeg 二进制」都排除在版本库外，新克隆必定缺件；
  而各池 manifest.json 里仍记着 3 万条条目。没有自检时，「环境缺件」和
  「代码有 bug」两种情况在报错上长得一模一样，排查会一路走错方向。

检查项：
  1. ffmpeg / ffprobe 解析结果（bin/ 优先 → PATH）
  2. 每个素材池：manifest 条目数 vs 磁盘实际文件数 vs 缺失条目数
  3. （可选 --hash N）抽样重算 sha256，报告与 manifest 记录不符的比例
  4. （可选 --run-tests）跑 remix 冒烟测试

用法：
  python remix/tools/doctor.py
  python remix/tools/doctor.py --hash 200 --run-tests
  python remix/tools/doctor.py --json

退出码：
  0  全部通过
  1  有告警（如素材缺失 —— 干净克隆下的预期状态）
  2  硬失败（ffmpeg 缺失 / remix 冒烟测试失败）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys

_REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REMIX_DIR not in sys.path:
    sys.path.insert(0, _REMIX_DIR)  # 本机 PYTHONSAFEPATH=1，脚本目录不自动入 sys.path

from core import binfind  # noqa: E402

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff", ".aif")
POOLS = ("bass", "drum", "guita", "cowbell", "synth", "animal", "sfx",
         "acapella", "keys", "strings", "brass", "woodwind", "ethnic")


def _pool_report(root: str, pool: str, hash_sample: int, rng: random.Random) -> dict:
    pdir = os.path.join(root, pool)
    mpath = os.path.join(pdir, "manifest.json")
    entries: list[dict] = []
    if os.path.isfile(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                entries = json.load(f).get("entries", []) or []
        except Exception as e:  # noqa: BLE001
            return {"pool": pool, "error": f"manifest 读取失败: {type(e).__name__}: {e}"}

    on_disk: set[str] = set()
    if os.path.isdir(pdir):
        for _r, _d, names in os.walk(pdir):
            for n in names:
                if n.lower().endswith(AUDIO_EXT):
                    on_disk.add(n)

    listed = {e.get("file") for e in entries if isinstance(e, dict) and e.get("file")}
    missing = len(listed - on_disk)
    extra = len(on_disk - listed)

    # 抽样哈希核对（仅对磁盘上确实存在的文件）
    hashed = mismatched = 0
    if hash_sample > 0 and on_disk:
        candidates = [(e, e["file"]) for e in entries
                      if isinstance(e, dict) and e.get("file") in on_disk
                      and e.get("sha256")]
        rng.shuffle(candidates)
        for entry, name in candidates[:hash_sample]:
            path = None
            for _r, _d, names in os.walk(pdir):
                if name in names:
                    path = os.path.join(_r, name)
                    break
            if not path:
                continue
            try:
                h = hashlib.sha256()
                with open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                continue
            hashed += 1
            if h.hexdigest() != entry.get("sha256"):
                mismatched += 1

    return {
        "pool": pool,
        "manifest_entries": len(entries),
        "files_on_disk": len(on_disk),
        "missing_on_disk": missing,
        "unlisted_on_disk": extra,
        "hashed": hashed,
        "hash_mismatch": mismatched,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="musickit 环境与素材一致性自检")
    ap.add_argument("--root", default=os.environ.get("MUSICKIT_ROOT")
                    or os.path.dirname(_REMIX_DIR), help="素材根目录（默认仓库根）")
    ap.add_argument("--hash", type=int, default=0, metavar="N",
                    help="每池抽样 N 个文件重算 sha256（0=不抽样）")
    ap.add_argument("--run-tests", action="store_true", help="顺带跑 remix 冒烟测试")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--strict", action="store_true", help="素材缺失也算失败（exit 2）")
    args = ap.parse_args()

    root = args.root
    rng = random.Random(42)
    bin_status = binfind.status()

    pools = [_pool_report(root, p, args.hash, rng) for p in POOLS]
    total_listed = sum(p.get("manifest_entries", 0) for p in pools)
    total_disk = sum(p.get("files_on_disk", 0) for p in pools)
    total_missing = sum(p.get("missing_on_disk", 0) for p in pools)
    total_hashed = sum(p.get("hashed", 0) for p in pools)
    total_mismatch = sum(p.get("hash_mismatch", 0) for p in pools)

    test_result = None
    if args.run_tests:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "-m", "smoke"],
            cwd=_REMIX_DIR, capture_output=True, text=True, env=env, timeout=600,
        )
        test_result = {"exit": proc.returncode,
                       "tail": (proc.stdout or "").strip().splitlines()[-1:]}

    hard_fail = []
    warnings = []
    if not bin_status["ffmpeg"]:
        hard_fail.append("ffmpeg 未找到（bin/ 与 PATH 均无）—— 渲染无法进行")
    if not bin_status["ffprobe"]:
        warnings.append("ffprobe 未找到 —— 时长探测将退回 soundfile，mp3/m4a 可能不准")
    if test_result and test_result["exit"] != 0:
        hard_fail.append(f"冒烟测试失败（exit {test_result['exit']}）")
    if total_disk == 0:
        warnings.append(f"素材池为空（manifest 记着 {total_listed} 条，磁盘 0 个文件）"
                        "—— 干净克隆下的预期状态；要渲染需先恢复素材")
    elif total_missing:
        warnings.append(f"{total_missing} 条 manifest 记录在磁盘上找不到对应文件")
    if total_hashed and total_mismatch:
        warnings.append(f"抽样 {total_hashed} 个文件，{total_mismatch} 个 sha256 与 manifest 不符")

    if args.strict and total_disk == 0:
        hard_fail.append("--strict：素材池为空")

    exit_code = 2 if hard_fail else (1 if warnings else 0)

    if args.json:
        print(json.dumps({
            "root": root, "bin": bin_status, "pools": pools,
            "summary": {"listed": total_listed, "on_disk": total_disk,
                        "missing": total_missing, "hashed": total_hashed,
                        "hash_mismatch": total_mismatch},
            "tests": test_result, "hard_fail": hard_fail,
            "warnings": warnings, "exit": exit_code,
        }, ensure_ascii=False, indent=2))
        return exit_code

    print("=" * 66)
    print("musickit doctor · 环境与素材自检")
    print("=" * 66)
    print(f"素材根目录 : {root}")
    print(f"bin 目录   : {bin_status['bin_dir']} (存在={bin_status['bin_dir_exists']})")
    print(f"ffmpeg     : {bin_status['ffmpeg'] or '❌ 未找到'}")
    print(f"ffprobe    : {bin_status['ffprobe'] or '⚠️ 未找到（时长探测退回 soundfile）'}")
    print()
    print(f"{'池':<10}{'manifest':>10}{'磁盘':>8}{'缺失':>8}{'未登记':>8}{'哈希不符':>10}")
    print("-" * 66)
    for p in pools:
        if "error" in p:
            print(f"{p['pool']:<10}  {p['error']}")
            continue
        hm = f"{p['hash_mismatch']}/{p['hashed']}" if p["hashed"] else "-"
        print(f"{p['pool']:<10}{p['manifest_entries']:>10}{p['files_on_disk']:>8}"
              f"{p['missing_on_disk']:>8}{p['unlisted_on_disk']:>8}{hm:>10}")
    print("-" * 66)
    print(f"{'合计':<10}{total_listed:>10}{total_disk:>8}{total_missing:>8}")
    if test_result:
        print(f"\n冒烟测试   : exit={test_result['exit']}  {test_result['tail']}")
    print()
    if hard_fail:
        print("❌ 硬失败：")
        for x in hard_fail:
            print(f"   - {x}")
    if warnings:
        print("⚠️ 告警：")
        for x in warnings:
            print(f"   - {x}")
    if not hard_fail and not warnings:
        print("✅ 全部检查通过")
    print(f"\n退出码 {exit_code}（0=通过 / 1=告警 / 2=硬失败）")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
