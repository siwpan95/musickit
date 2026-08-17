"""musickit Phase 1 去重工具 —— 把 cowbell / synth 的重复副本移入 archived 垃圾桶。

判定：内容签名相同（文件大小 + 首尾各 64KB 的 SHA-256）。
保留：每个签名组中编号最小的文件（如 "cowbell (1).mp3" 组内保留，"(109)/(115)/(7)" 移走）。
目标：G:\\musickit\\archived\\dedupe_<来源目录>\\  —— 只 move 不 delete，全程写 manifest。

用法：
    python dedupe_to_archive.py            # dry-run（默认），只打印计划
    python dedupe_to_archive.py --apply    # 执行移动
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from datetime import datetime

ROOT = r"G:\musickit"
ARCHIVE = os.path.join(ROOT, "archived")
SOURCES = {
    "cowbell": "dedupe_cowbell",
    "synth": "dedupe_synth",
}
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "dedupe_manifest.json")


def partial_hash(path, head=65536, tail=65536):
    """文件大小 + 首尾各 64KB 的 SHA-256，用于快速判重。"""
    size = os.path.getsize(path)
    h = hashlib.sha256()
    h.update(struct.pack("<Q", size))
    with open(path, "rb") as f:
        h.update(f.read(head))
        if size > head + tail:
            f.seek(size - tail)
            h.update(f.read(tail))
    return h.hexdigest()


def natural_key(name):
    """从 "xxx (12).ext" 提取 12 作排序键，便于保留最小编号。"""
    m = re.search(r"\((\d+)\)", name)
    return int(m.group(1)) if m else 10**9


def collect_groups(src_dir):
    """返回 {签名: [文件名列表]}，仅含音频文件。"""
    groups = {}
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith(AUDIO_EXT):
            continue
        fp = os.path.join(src_dir, name)
        sig = partial_hash(fp)
        groups.setdefault(sig, []).append(name)
    return groups


def build_plan():
    """扫描 cowbell / synth，产出待移动清单与统计。"""
    plan = []
    stats = {}
    for src, sub in SOURCES.items():
        src_dir = os.path.join(ROOT, src)
        if not os.path.isdir(src_dir):
            print(f"[warn] {src_dir} 不存在，跳过")
            continue
        groups = collect_groups(src_dir)
        kept, moved = 0, 0
        for sig, names in groups.items():
            names_sorted = sorted(names, key=natural_key)
            keeper = names_sorted[0]
            kept += 1
            for dup in names_sorted[1:]:
                plan.append({
                    "src": os.path.join(src_dir, dup),
                    "dst": os.path.join(ARCHIVE, sub, dup),
                    "sig": sig[:16],
                })
                moved += 1
        stats[src] = {"files": kept + moved, "unique_kept": kept, "dup_to_move": moved,
                      "groups": len(groups)}
    return plan, stats


def main():
    ap = argparse.ArgumentParser(description="musickit 去重转移工具（只 move 不 delete）")
    ap.add_argument("--apply", action="store_true", help="执行移动（默认仅 dry-run）")
    args = ap.parse_args()

    plan, stats = build_plan()
    print("== 去重计划 ==")
    for src, s in stats.items():
        print(f"[{src}] 共 {s['files']} 个 → 保留 {s['unique_kept']} 个唯一，"
              f"移走 {s['dup_to_move']} 个重复副本（{s['groups']} 个签名组）")
    print(f"合计待移动: {len(plan)} 个文件 → {ARCHIVE}")

    manifest = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "dry_run": not args.apply,
        "stats": stats,
        "moves": plan,
    }
    if not args.apply:
        print("\n== dry-run：以下文件将被移动 ==")
        for m in plan[:60]:
            print(f"  {os.path.basename(m['src'])} → archived/{os.path.basename(os.path.dirname(m['dst']))}/")
        if len(plan) > 60:
            print(f"  ... 共 {len(plan)} 条，完整清单见 {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"\n计划已写入 {MANIFEST_PATH}\n（确认无误后运行: python dedupe_to_archive.py --apply）")
        return

    # ---- 执行 ----
    ok, fail = 0, 0
    for m in plan:
        try:
            os.makedirs(os.path.dirname(m["dst"]), exist_ok=True)
            if os.path.exists(m["dst"]):
                raise FileExistsError(f"目标已存在: {m['dst']}")
            shutil.move(m["src"], m["dst"])
            ok += 1
        except Exception as e:
            fail += 1
            m["error"] = str(e)
            print(f"[fail] {m['src']} → {e}", file=sys.stderr)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"\n== 执行完成：成功 {ok}，失败 {fail} ==")
    for src, s in stats.items():
        print(f"[{src}] 剩余文件数: {s['unique_kept']}（预期）")
    # 复查
    leftover, _ = build_plan()
    print(f"复查：再跑一次扫描，剩余可去重数为 {len(leftover)}（应为 0）")
    print(f"移动记录: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
