"""Phase 4：构建 musickit 总索引 manifest_index.json。

1. 合并各素材目录的 manifest.json（bass/drum/guita/cowbell/synth/animal/sfx/acapella）
2. 把 bass/drum/guita 的匿名编号 stem 反查歌名：与 <STEMS_ROOT>（默认 <工作区>\\assets\\radio_music_stems）
   各歌曲目录下的 bass.wav/drums.wav/other.wav 做「大小+前 8KB 哈希」匹配
3. 索引级纳入 <CSMUSIC_STEMS_ROOT>（默认 <工作区>\\csmusic_stems）（CS 游戏音乐分离库，持续增⻓中）：
   逐曲扫描每首歌曲目录，记录 4 种 stem（bass/drums/other/vocals）的
   存在性、尺寸与签名，并标注「进行中」状态（含 htdemucs 临时目录或
   stem 不足 4 个的目录）。仅索引，不合并、不改动物料。
4. 输出 <MUSICKIT_ROOT>\\manifest_index.json
用法: python build_manifest_index.py
"""
import hashlib
import json
import os
import struct
from datetime import datetime
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

ROOT = str(_MK_ROOT)
# 2026-09-23 去本地化：stem 库已归位到 <工作区>\assets\*（原路径已失效）
_WORKSPACE = _MK_ROOT.parent.parent                       # …\<盘>\
STEMS = str(Path(os.environ.get("STEMS_ROOT") or (_WORKSPACE / "assets" / "radio_music_stems")))
CS_STEMS = str(Path(os.environ.get("CSMUSIC_STEMS_ROOT") or (_WORKSPACE / "assets" / "csmusic_stems")))
CATEGORIES = [
    "bass", "drum", "guita", "cowbell", "synth", "animal", "sfx", "acapella",
    # 新增：37 类目补齐
    "keys", "strings", "brass", "woodwind", "ethnic",
]
STEM_KIND = {"bass": "bass.wav", "drum": "drums.wav", "guita": "other.wav"}
CS_STEM_FILES = ["bass.wav", "drums.wav", "other.wav", "vocals.wav"]
CS_STEM_KIND = {"bass.wav": "bass", "drums.wav": "drums",
                "other.wav": "other", "vocals.wav": "vocals"}


def quick_sig(path, head=8192):
    size = os.path.getsize(path)
    h = hashlib.sha256()
    h.update(struct.pack("<Q", size))
    with open(path, "rb") as f:
        h.update(f.read(head))
    return h.hexdigest()


def build_csmusic_block(merged_songs=None):
    """索引级纳入 <CSMUSIC_STEMS_ROOT>（默认 <工作区>\\csmusic_stems）：逐曲列出 stem，标注「进行中」与「已并入物料」状态。仅索引不改动物料。"""
    merged_songs = set(merged_songs or set())
    block = {
        "dir": CS_STEMS,
        "note": "CS 游戏音乐 Demucs 分离库，持续增⻓中；物料已通过 ingest_csmusic.py 增量并入 musickit 编号目录（见 stems_song_map）",
        "song_count": 0,
        "complete_count": 0,
        "merged_count": 0,
        "incomplete": [],
        "songs": {},
    }
    if not os.path.isdir(CS_STEMS):
        return block
    for song in sorted(os.listdir(CS_STEMS)):
        dp = os.path.join(CS_STEMS, song)
        if not os.path.isdir(dp):
            continue
        stems = {}
        present = []
        subdirs = []
        for fn in os.listdir(dp):
            fp = os.path.join(dp, fn)
            if os.path.isdir(fp):
                subdirs.append(fn)
                continue
            if fn in CS_STEM_FILES:
                size = os.path.getsize(fp)
                stems[CS_STEM_KIND[fn]] = {
                    "file": fn,
                    "size": size,
                    "sig": quick_sig(fp)[:16],
                }
                present.append(CS_STEM_KIND[fn])
        # 完整 = 4 种 stem 齐全 且 无子目录（htdemucs 临时目录 => 分离进行中）
        complete = len(present) == 4 and not subdirs
        status = "complete" if complete else "in_progress"
        block["song_count"] += 1
        if complete:
            block["complete_count"] += 1
        else:
            block["incomplete"].append(song)
        is_merged = song in merged_songs
        if is_merged:
            block["merged_count"] += 1
        block["songs"][song] = {
            "rel": dp,
            "stems_present": present,
            "stems": stems,
            "status": status,
            "merged_into_musickit": is_merged,
        }
    return block


def main():
    index = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "categories": {},
        "stems_song_map": {},
        "stats": {},
    }

    # 1) 合并 manifest
    for cat in CATEGORIES:
        mp = os.path.join(ROOT, cat, "manifest.json")
        entries = []
        if os.path.exists(mp):
            with open(mp, "r", encoding="utf-8") as f:
                entries = json.load(f).get("entries", [])
        # 统计目录实际音频文件数（递归，兼容含子目录的分类如 acapella）
        cat_dir = os.path.join(ROOT, cat)
        n_audio = 0
        for _root, _dirs, _files in os.walk(cat_dir):
            for _f in _files:
                if _f.lower().endswith((".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".aiff", ".aif")):
                    n_audio += 1
        index["categories"][cat] = {
            "dir": os.path.join(ROOT, cat),
            "audio_files": n_audio,
            "manifest_entries": len(entries),
            "entries": entries,
        }
        index["stats"][cat] = {"files": n_audio, "manifested": len(entries)}

    # 2) stem 歌名反查（bass/drum/guita）
    print("构建 radio_music_stems 签名表 ...")
    sig2song = {}
    n_scanned = 0
    for cat, kind in STEM_KIND.items():
        for song_dir in os.listdir(STEMS):
            p = os.path.join(STEMS, song_dir, kind)
            if os.path.isfile(p):
                sig2song[quick_sig(p)] = (song_dir, cat)
                n_scanned += 1
    print(f"stems 签名 {n_scanned} 条")

    for cat in ("bass", "drum", "guita"):
        cat_dir = os.path.join(ROOT, cat)
        mapped = 0
        for _root, _dirs, _files in os.walk(cat_dir):
            for name in sorted(_files):
                if not name.lower().endswith(".wav"):
                    continue
                fp = os.path.join(_root, name)
                rel = os.path.relpath(fp, ROOT).replace("\\", "/")
                sig = quick_sig(fp)
                hit = sig2song.get(sig)
                if hit:
                    index["stems_song_map"][rel] = {"song": hit[0], "stem_kind": hit[1]}
                    mapped += 1
        index["stats"][f"{cat}_song_mapped"] = mapped
        print(f"[{cat}] 歌名映射 {mapped} 个")

    # 3) csmusic_stems 索引级纳入（持续增⻓源，仅索引不合并）
    # 已并入 musickit 物料的 csmusic 歌曲（来自 manifest source_pack=="csmusic"）
    cs_merged = set()
    for cat in ("bass", "drum", "guita"):
        for e in index["categories"][cat]["entries"]:
            if e.get("source_pack") == "csmusic" and e.get("original"):
                cs_merged.add(e["original"])
    print("索引级纳入 csmusic_stems ...")
    cs = build_csmusic_block(merged_songs=cs_merged)
    index["csmusic_stems"] = cs
    index["stats"]["csmusic_stems"] = {
        "songs": cs["song_count"],
        "complete": cs["complete_count"],
        "in_progress": len(cs["incomplete"]),
        "merged_into_musickit": cs["merged_count"],
    }
    # csmusic 歌名映射并入 stems_song_map（直接读 manifest，无需哈希反查）
    cs_map = 0
    for cat in ("bass", "drum", "guita"):
        for e in index["categories"][cat]["entries"]:
            if e.get("source_pack") == "csmusic":
                index["stems_song_map"][f"{cat}/{e['file']}"] = {
                    "song": e["original"], "stem_kind": cat, "source": "csmusic",
                }
                cs_map += 1
    index["stats"]["csmusic_mapped"] = cs_map
    print(f"csmusic_stems: {cs['song_count']} 曲（完成 {cs['complete_count']} / "
          f"进行中 {len(cs['incomplete'])} / 已并入物料 {cs['merged_count']}）")
    print(f"[csmusic] stems_song_map 新增 {cs_map} 条（来自 manifest）")

    out = os.path.join(ROOT, "manifest_index.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
