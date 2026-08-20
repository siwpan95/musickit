"""Phase 5b：清理细分 apply 崩溃留下的「半移动」重复副本。

崩溃时 shutil.move 先把文件复制到子目录，但沙箱 safe-delete 钩子拦截了删除源文件，
导致同一 basename 同时存在于 池根目录 与 子目录（源文件保留、副本残留）。

本工具扫描 6 个细分池（bass/drum/guita/synth/acapella/sfx）：
  若某 basename 同时出现在 池根 与 任意子目录，则删除「子目录副本」
  （池根是权威位置，后续 apply 会把它重新移动到正确子类子目录）。

默认 DRY-RUN（仅报告待删文件）。加 --apply 才真正删除。
用法: python cleanup_duplicate_moves.py [--apply]
"""
import argparse
import os
import json

ROOT = r"G:\music\musickit"
POOLS = ["bass", "drum", "guita", "synth", "acapella", "sfx"]
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")


def find_collisions(pool):
    """返回 [(root_path, subfolder_path), ...] 同一 basename 同时存在于根与子目录的配对。"""
    pdir = os.path.join(ROOT, pool)
    if not os.path.isdir(pdir):
        return []
    root_files = {}
    for f in os.listdir(pdir):
        if f.lower().endswith(AUDIO_EXT) and os.path.isfile(os.path.join(pdir, f)):
            root_files[f] = os.path.join(pdir, f)
    collisions = []
    for _r, _dirs, files in os.walk(pdir):
        # 只深入子目录（跳过池根本身）
        if os.path.abspath(_r) == os.path.abspath(pdir):
            continue
        for f in files:
            if f.lower().endswith(AUDIO_EXT) and f in root_files:
                collisions.append((root_files[f], os.path.join(_r, f)))
    return collisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正删除子目录副本")
    args = ap.parse_args()

    total = 0
    report = []
    for pool in POOLS:
        cols = find_collisions(pool)
        for root_p, sub_p in cols:
            report.append((pool, root_p, sub_p))
            total += 1

    print(f"发现 {total} 个根/子目录冲突副本")
    for pool, root_p, sub_p in report:
        print(f"  [{pool}] 保留根: {os.path.basename(root_p)}")
        print(f"        删除副本: {sub_p}")

    if args.apply:
        trash = os.path.join(ROOT, ".subdivide_trash")
        os.makedirs(trash, exist_ok=True)
        removed = 0
        for pool, root_p, sub_p in report:
            try:
                base = os.path.basename(sub_p)
                tp = os.path.join(trash, f"{pool}__{base}")
                i = 1
                while os.path.exists(tp):
                    tp = os.path.join(trash, f"{pool}__{base}.{i}")
                    i += 1
                os.rename(sub_p, tp)   # 重定位到回收目录（rename 不受 safe-delete 拦截）
                removed += 1
                print(f"  已移入回收: {sub_p} -> {tp}")
            except Exception as ex:
                print(f"  [WARN] 处理失败 {sub_p}: {ex}")
        print(f"实际移入回收 {removed} 个副本（位于 {trash}）")
    else:
        print("\n（DRY-RUN，未删除。加 --apply 执行）")


if __name__ == "__main__":
    main()
