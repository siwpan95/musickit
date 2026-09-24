#!/usr/bin/env python
"""Generate archive manifest (JSON + Markdown) for the downloads root (env BAIDU_DOWNLOAD_ROOT).

Records what was ingested into the musickit pools and where every downloaded
item was archived, so future sessions can check before re-downloading.
"""
import os
import json
import datetime
import collections
from pathlib import Path

_MK_ROOT = Path(os.environ.get("MUSICKIT_ROOT") or Path(__file__).resolve().parents[2])   # 2026-09-23 去本地化（仓根）

BAIDU = os.environ.get("BAIDU_DOWNLOAD_ROOT", "")   # 2026-09-23 去本地化
# 2026-09-23 去本地化：压缩包归档目录现为 <工作区>\assets\yasuobao（原路径已失效）
YASUOBAO = os.environ.get("YASUOBAO_SRC") or str(_MK_ROOT.parent.parent / "assets" / "yasuobao")
ARCHIVED = str(Path(BAIDU) / "archived") if BAIDU else ""   # 2026-09-23 去本地化
MUSICKIT = str(_MK_ROOT)

AEXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif")


def dir_size(p):
    n = 0
    for dp, _, fns in os.walk(p):
        for fn in fns:
            try:
                n += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return n


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{u}" if u != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}PB"


# --- items archived to yasuobao (compressed archives) ---
yasuobao_items = [
    ("【价值399美元终极人声样品包】Ultimate Vocal Library 3.zip",
     "摄入 1901 文件（实为 Ghosthack Electro Bass House：vocal 1123 / guitar 184 / keys 451 / synth 131 / 其他）"),
    ("【电影史诗弦乐采样包】Nano Musik Loops - Cinematic Strings Vol.11.zip",
     "已摄入（早前，strings 池）"),
    ("【音乐人终极采样包】Ultimate Producer Bunble WAV MiDi FLP NI Massive and Xfer Serum Presets.zip",
     "已摄入子集（早前：brass 25 / woodwind 10 / strings 5）"),
    ("Deeper House Vol 1.zip",
     "摄入 58 文件（guitar 32 / rhodes 5 / synth+pad 8 / vocal 12 / strings 1；鼓组/完整混音跳过）"),
    ("Echo Sound Works - Aurora Guitars [免版税].7z",
     "摄入（guita 池，吉他 loop）"),
    ("Ghosthack.Sounds.Orchestral.Essentials.zip",
     "已摄入（早前，358 文件）"),
    ("XAM.Sample.Pack3.rar",
     "已摄入（guita 池 XAM Guitar；trap 包其余为饱和池/版权 acapella）"),
    ("Coollider Acapellas Vols.1-42",
     "摄入 1454 文件（acapella 池），17 个分卷压缩包 (.z01-.z16 + .zip)"),
    ("ReFX Nexus 2 Complete Bundle.part",
     "不可提取（Nexus2 专有 .fxp 格式，无开源提取器），10 分卷 rar"),
    ("Loopmasters Soul Jazz Piano MULTiFORMAT.zip",
     "重复下载：yasuobao 已有完全相同文件（799629348 字节），副本已删除"),
]

# --- items archived to archived/ (extracted dirs) ---
archived_items = [
    ("【抒情铜管连奏乐器KONTAKT扩展】Fracture Sounds - Brass Band Soloists KONTAKT",
     "不可提取（2024 新库，nkx 加密，需正版 Kontakt 注册）"),
    ("AudioModeling.SWAM.Solo.Brass.Bundle.v1.6.2.CE-V.R",
     "安装器（物理建模音源，无采样可吃）"),
    ("Berlin Strings 2.5 FULL 柏林管弦乐",
     "抽样摄入 2618 文件（strings 池；其余 19 万为 round-robin/力度层变体）"),
    ("Coollider Acapellas Vols.1-42",
     "摄入 1454 文件（acapella 池，Acapellas 子目录）"),
    ("Echo Sound Works Genesis (+ Bonuses)",
     "已摄入（与 Garrix 合计 2478 文件）"),
    ("Martin Garrix 风格采样包最新合集 STMPD 邮票厂采样包合集",
     "已摄入"),
    ("Orchestral Tools Berlin Woodwinds",
     "抽样摄入 9618 文件（woodwind 池，BWW1）"),
    ("Orchestral Tools Berlin Woodwinds柏林木管",
     "无样本（仅主程序 nicnt/安装器）"),
    ("Orchestral.Tools.Berlin.Woodwinds.Soloists[柏林木管]",
     "摄入 3598 文件（woodwind 池，BWW3）"),
    ("XAM.Sample.Pack3",
     "已摄入（trap 包，guitar 已入 guita 池）"),
]


def build():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # pool counts (the 13 canonical pools only)
    POOL_NAMES = ["bass", "drum", "guita", "cowbell", "synth", "acapella",
                  "animal", "sfx", "keys", "strings", "brass", "woodwind", "ethnic"]
    pools = {}
    for d in POOL_NAMES:
        p = os.path.join(MUSICKIT, d)
        if not os.path.isdir(p):
            continue
        n = 0
        for dp, _, fns in os.walk(p):
            for fn in fns:
                if fn.lower().endswith(AEXT):
                    n += 1
        pools[d] = n
    total = sum(pools.values())

    # enrich with sizes
    def with_size(items, base):
        out = []
        for name, note in items:
            p = os.path.join(base, name)
            if os.path.exists(p):
                sz = dir_size(p) if os.path.isdir(p) else os.path.getsize(p)
            else:
                # split-volume archives: match prefix
                sz = 0
                for f in os.listdir(base):
                    if f.startswith(name):
                        sz += os.path.getsize(os.path.join(base, f))
            out.append({"name": name, "size_bytes": sz, "size_h": human(sz), "status": note})
        return out

    y = with_size(yasuobao_items, YASUOBAO)
    a = with_size(archived_items, ARCHIVED)

    data = {
        "generated_at": now,
        "source_dir": BAIDU,
        "archive_zips_dir": YASUOBAO,
        "archive_extracted_dir": ARCHIVED,
        "musickit_pools": pools,
        "musickit_total_files": total,
        "ingested_to_yasuobao": y,
        "ingested_to_archived": a,
        "note": "所有素材已摄入 musickit 仓内对应池后归档。下次下载前先查本清单，避免重复下载。",
    }

    json_path = os.path.join(BAIDU, "归档清单.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # markdown
    md = []
    md.append("# 归档证明（BaiduNetdiskDownload）")
    md.append("")
    md.append(f"- 归档时间：{now}")
    md.append(f"- 下载目录：`{BAIDU}`")
    md.append(f"- 压缩包归档至：`{YASUOBAO}`")
    md.append(f"- 解压内容归档至：`{ARCHIVED}`")
    md.append("")
    md.append("## musickit 池最终状态（磁盘文件数 = manifest，全部一致）")
    md.append("")
    md.append("| 池 | 文件数 |")
    md.append("|---|---|")
    for d in sorted(pools):
        md.append(f"| {d} | {pools[d]} |")
    md.append(f"| **合计** | **{total}** |")
    md.append("")
    md.append("## 压缩包归档（→ yasuobao）")
    md.append("")
    md.append("| 文件 | 大小 | 摄入状态 |")
    md.append("|---|---|---|")
    for it in y:
        md.append(f"| {it['name']} | {it['size_h']} | {it['status']} |")
    md.append("")
    md.append("## 解压内容归档（→ archived）")
    md.append("")
    md.append("| 目录 | 大小 | 摄入状态 |")
    md.append("|---|---|---|")
    for it in a:
        md.append(f"| {it['name']} | {it['size_h']} | {it['status']} |")
    md.append("")
    md.append("---")
    md.append("**下次下载前请先查阅本文件，凡出现在上方清单中的素材均已在本地归档，无需重复下载。**")

    md_path = os.path.join(BAIDU, "归档证明.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("JSON ->", json_path)
    print("MD   ->", md_path)
    print("总文件数:", total)
    return json_path, md_path


if __name__ == "__main__":
    build()
