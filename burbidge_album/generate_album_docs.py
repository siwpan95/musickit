#!/usr/bin/env python3
# generate_album_docs.py - Build the Mix Engineer Series documentation from
# album/styles_manifest.json (produced by build_album.py):
#   album/index.html         hub page (one card per mixer)
#   album/ALBUM_NOTES.md     full multi-style notes
#   album/cover.svg          series cover
#   album/<slug>/index.html  per-style player page
#   album/<slug>/cover.svg   per-style cover
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
ALBUM = os.path.join(HERE, "album")
MANIFEST = os.path.join(ALBUM, "styles_manifest.json")
OUT_MD = os.path.join(ALBUM, "ALBUM_NOTES.md")
OUT_HTML = os.path.join(ALBUM, "index.html")
OUT_COVER = os.path.join(ALBUM, "cover.svg")

ALBUM_TITLE = "After Midnight"
SERIES = "The Mix Engineer Series"
ARTIST = "Compiled & mixed with musickit stems"

def load_data():
    return json.load(open(MANIFEST, encoding="utf-8"))["styles"]   # 2026-09-23 修复：未指定编码时中文 Windows 用 GBK 解码 UTF-8 会崩

def esc(s): return html.escape(str(s)) if s else "—"

STAGE_LABELS = {
    "drums": "Drums",
    "bass": "Bass",
    "pad": "Harmony/pad",
    "lead": "Lead (the 'voice')",
    "bg": "Background",
    "master": "Master bus",
}

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def mix_hex(hexa, t):
    """blend accent toward black: t=0 -> black, t=1 -> accent"""
    r, g, b = hex_rgb(hexa)
    return "#%02x%02x%02x" % (int(r*t), int(g*t), int(b*t))

# ---------------- per-style cover svg ----------------
def style_cover(st):
    c = st["color"]
    bg1, bg2 = mix_hex(c, 0.13), "#07060a"
    name = st["name"].upper()
    zh = st["zh"]
    tag = st["tagline"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{bg1}"/>
      <stop offset="1" stop-color="{bg2}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.32" r="0.7">
      <stop offset="0" stop-color="{c}" stop-opacity="0.32"/>
      <stop offset="1" stop-color="{c}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="800" fill="url(#bg)"/>
  <rect width="800" height="800" fill="url(#glow)"/>
  <g fill="none" stroke="{c}" stroke-opacity="0.55">
    <circle cx="400" cy="295" r="150"/>
    <circle cx="400" cy="295" r="110"/>
    <circle cx="400" cy="295" r="70"/>
  </g>
  <text x="400" y="295" text-anchor="middle" font-family="Georgia, serif" font-size="36" fill="#f3e2bd" font-style="italic">After Midnight</text>
  <text x="400" y="545" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="30" letter-spacing="6" fill="{c}">{esc(name)}</text>
  <text x="400" y="585" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="16" letter-spacing="2" fill="#b9ab92">{esc(zh)}</text>
  <text x="400" y="620" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="14" letter-spacing="2" fill="#9c8e74">MIX ENGINEER SERIES · musickit STEMS</text>
  <text x="400" y="700" text-anchor="middle" font-family="Georgia, serif" font-size="16" fill="#8a7d66" font-style="italic">{esc(tag)}</text>
</svg>'''

# ---------------- series cover ----------------
def series_cover():
    data = load_data()
    dots = "".join(
        f'<circle cx="{80 + i*70}" cy="660" r="10" fill="{st["color"]}" fill-opacity="0.85"/>'
        for i, st in enumerate(data))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#151210"/>
      <stop offset="1" stop-color="#07060a"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.32" r="0.7">
      <stop offset="0" stop-color="#d9a441" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#d9a441" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="800" fill="url(#bg)"/>
  <rect width="800" height="800" fill="url(#glow)"/>
  <g fill="none" stroke="#d9a441" stroke-opacity="0.45">
    <circle cx="400" cy="285" r="150"/>
    <circle cx="400" cy="285" r="110"/>
    <circle cx="400" cy="285" r="70"/>
  </g>
  <text x="400" y="285" text-anchor="middle" font-family="Georgia, serif" font-size="42" fill="#f3e2bd" font-style="italic">After Midnight</text>
  <text x="400" y="470" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="26" letter-spacing="8" fill="#d9a441">THE MIX ENGINEER SERIES</text>
  <text x="400" y="510" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="15" letter-spacing="3" fill="#9c8e74">SIX TRACKS × {len(data)} MIXERS · SAME STEMS · TEN PHILOSOPHIES</text>
  <g>{dots}</g>
  <text x="400" y="715" text-anchor="middle" font-family="Georgia, serif" font-size="16" fill="#7a6e58" font-style="italic">one arrangement, {len(data)} consoles of character</text>
</svg>'''

# ---------------- markdown notes ----------------
def chain_rows_md(st):
    rows = []
    for key in ("drums", "bass", "pad", "lead", "bg", "master"):
        rows.append(f"| {STAGE_LABELS[key]} | {st['sig'][key]} | {st['impl'][key]} |")
    return "\n".join(rows)

def track_rows_md(st):
    rows = []
    for t in st["tracks"]:
        rows.append(f"| {t['num']:02d} | {esc(t['title'])} | {t['tempo']} BPM | {esc(t['key'])} | {t['dur']} s | {t['lufs']} |")
    return "\n".join(rows)

def write_markdown():
    data = load_data()
    lines = []
    lines.append(f"# After Midnight — The Mix Engineer Series ({len(data)} Mixers × 6 Tracks)\n")
    lines.append(f"**{ARTIST}**  \n")
    lines.append("Six instrumental R&B/soul tracks assembled from the musickit sample library. "
                 "**The same six tracks, the same stems, the same arrangement** are mixed through "
                 f"{len(data)} different mixing engineers' signature chains — from Craig Burbidge's "
                 "vocal-forward warmth to Al Schmitt's natural transparency and Mike Dean's saturated "
                 "psychedelia — so the styles can be A/B-compared directly. Each chain is a "
                 "parameterization of the zero-dependency DSP toolkit in dsp.py (biquad EQ, "
                 "feed-forward compression, tanh saturation, convolution plate/room reverb, M/S "
                 "width, brickwall limiting).\n")
    lines.append(f"\n## The {len(data)} mixers at a glance\n")
    lines.append("| # | Mixer | 中文 | Reference artists | Signature | Target LUFS |")
    lines.append("|---|---|---|---|---|---|")
    for i, st in enumerate(data, 1):
        lines.append(f"| {i} | {esc(st['name'])} | {esc(st['zh'])} | {', '.join(esc(r) for r in st['refs'][:4])} | {esc(st['tagline'])} | {st['target_lufs']} |")
    for st in data:
        lines.append(f"\n## {st['name']} ({st['zh']}) — album/{st['folder']}/\n")
        lines.append(st["about"] + "\n")
        lines.append(f"- Reference artists: {', '.join(esc(r) for r in st['refs'])}.\n")
        lines.append(f"- Output folder: album/{st['folder']}/ — open album/{st['folder']}/index.html to listen.\n")
        lines.append("\n| Stage | Signature | This implementation |")
        lines.append("|---|---|---|")
        lines.append(chain_rows_md(st))
        lines.append("\n| # | Title | Tempo | Key | Duration | est. LUFS |")
        lines.append("|---|---|---|---|---|---|")
        lines.append(track_rows_md(st))
    first = data[0]
    lines.append("\n## Stems used (shared by every style)\n")
    for t in first["tracks"]:
        s = t.get("stems", {})
        lines.append(f"### {t['num']:02d}. {esc(t['title'])}  ({t['tempo']} BPM / {esc(t['key'])})\n")
        lines.append(f"- **Drums:** {esc(s.get('drum'))}\n")
        lines.append(f"- **Bass:** {esc(s.get('bass'))}\n")
        lines.append(f"- **Harmony/pad:** {esc(s.get('pad'))}\n")
        lines.append(f"- **Lead (the 'voice'):** {esc(s.get('lead'))}\n")
        lines.append(f"- **Background:** {esc(s.get('bg'))}\n")
        lines.append(f"- **SFX/transitions:** {esc(s.get('sfx'))}\n")
    lines.append("\n## Notes & honest limitations\n")
    lines.append("- **Identical arrangement across styles** is deliberate: it isolates the mixing "
                 "differences (balance, EQ, compression, space, width, loudness) from the "
                 "arrangement differences.\n")
    lines.append("- Instrumental by design: the musickit acapella set contains real famous-song "
                 "vocals (copyright), so the album is instrumental and a **lead instrument** is mixed "
                 "front-and-center in place of a vocal.\n")
    lines.append("- Harmonic compatibility is best-effort: stems are selected by matching root key where "
                 "the library exposes one; some layers may be modal neighbours rather than identical keys.\n")
    lines.append("- Tempo matching uses a pitch-preserving phase-vocoder time-stretch (ratio kept within "
                 "±20% of each stem's native BPM) so loops lock to the track tempo.\n")
    lines.append("- LUFS is a K-weighting RMS proxy for monitoring only, not a certified measurement.\n")
    lines.append("- Each 'mixer' is an interpretation of that engineer's documented signature expressed "
                 "with the same DSP primitives — a homage/study, not a claim of authentic hardware emulation.\n")
    lines.append("\n*Generated with build_album.py + generate_album_docs.py "
                 "(numpy/scipy/soundfile, zero external DSP deps).*\n")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines))
    print("wrote", OUT_MD)

# ---------------- html pages ----------------
BASE_CSS = '''
  body{margin:0;background:#0c0a0d;color:#e8e0d2;font-family:Helvetica,Arial,sans-serif}
  .wrap{max-width:760px;margin:0 auto;padding:32px 20px 60px}
  a{color:#d9a441;text-decoration:none}
  header{text-align:center;margin-bottom:28px}
  h1{font-family:Georgia,serif;font-style:italic;color:#f3e2bd;font-size:30px;margin:0 0 6px}
  .tag{letter-spacing:4px;font-size:13px}
  .cover{display:block;width:220px;margin:18px auto;border-radius:6px;box-shadow:0 10px 40px rgba(0,0,0,.6)}
  .back{display:inline-block;margin-bottom:10px;font-size:13px}
  table{width:100%;border-collapse:collapse;margin:14px 0 26px;font-size:13px}
  th,td{border:1px solid #26211c;padding:8px 10px;text-align:left;vertical-align:top}
  th{color:#d9a441;font-weight:normal;background:#141013}
  h2{font-size:16px;letter-spacing:2px;color:#d9a441;margin-top:30px;text-transform:uppercase}
  .about,.refs{font-size:14px;line-height:1.7;color:#b6ab97;margin:10px auto;max-width:640px}
  .refs{font-size:12.5px;color:#9c8e74}
  .track{display:flex;align-items:center;gap:16px;padding:14px 0;border-top:1px solid #211d1a}
  .num{font-family:Georgia,serif;font-size:22px;width:34px;text-align:center}
  .meta{flex:1}
  .title{font-size:16px;color:#f0e8da}
  .sub{font-size:12px;color:#9c8e74;margin-top:3px}
  audio{width:230px;height:34px}
  footer{margin-top:30px;text-align:center;color:#6f6555;font-size:12px;line-height:1.7}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:18px;margin-top:26px}
  .card{display:block;background:#141013;border:1px solid #26211c;border-radius:8px;padding:16px 14px;text-align:center;transition:border-color .2s}
  .card:hover{border-color:#d9a441}
  .card img{width:150px;border-radius:5px;margin-bottom:10px}
  .cname{font-size:16px;color:#f0e8da;font-family:Georgia,serif}
  .czh{font-size:12px;color:#9c8e74;margin-top:2px}
  .ctag{font-size:11.5px;color:#d9a441;margin-top:8px;line-height:1.5}
  .clufs{font-size:11px;color:#6f6555;margin-top:6px}
  .intro{text-align:center;color:#b6ab97;font-size:14px;line-height:1.7;max-width:640px;margin:0 auto}
'''

def track_card_html(t, accent):
    fn = os.path.basename(t["out"])
    return f'''
    <div class="track">
      <div class="num" style="color:{accent}">{t['num']:02d}</div>
      <div class="meta">
        <div class="title">{esc(t['title'])}</div>
        <div class="sub">{t['tempo']} BPM &middot; key {esc(t['key'])} &middot; {t['dur']}s &middot; ~{t['lufs']} LUFS</div>
      </div>
      <audio controls preload="none" src="{esc(fn)}"></audio>
    </div>'''

def chain_table_html(st):
    rows = []
    for key in ("drums", "bass", "pad", "lead", "bg", "master"):
        rows.append(f"<tr><td>{STAGE_LABELS[key]}</td><td>{esc(st['sig'][key])}</td><td>{esc(st['impl'][key])}</td></tr>")
    return f'''<h2>The chain</h2>
<table>
  <tr><th>Stage</th><th>Signature</th><th>Implementation</th></tr>
  {''.join(rows)}
</table>'''

def write_style_pages():
    data = load_data()
    for st in data:
        folder = os.path.join(ALBUM, st["folder"])
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "cover.svg"), "w", encoding="utf-8") as f:
            f.write(style_cover(st))
        cards = "".join(track_card_html(t, st["color"]) for t in st["tracks"])
        page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(ALBUM_TITLE)} — the {esc(st['name'])} mix</title>
<style>{BASE_CSS}</style></head>
<body><div class="wrap">
  <header>
    <a class="back" href="../index.html">&larr; All mixers</a>
    <h1>{esc(ALBUM_TITLE)}</h1>
    <div class="tag" style="color:{st['color']}">{esc(st['name'].upper())} · {esc(st['tagline'])}</div>
    <img class="cover" src="cover.svg" alt="cover">
    <p class="about">{esc(st['about'])}</p>
    <p class="refs">Reference artists: {', '.join(esc(r) for r in st['refs'])} · target ~{st['target_lufs']} LUFS</p>
  </header>
  {chain_table_html(st)}
  <h2>Tracks</h2>
  {cards}
  <footer>
    Same six tracks, same stems, same arrangement as every other style in this series —
    only the mixing philosophy changes. See <a href="../ALBUM_NOTES.md">ALBUM_NOTES.md</a>
    for the full series documentation.<br>
    Generated with <code>build_album.py</code> + <code>generate_album_docs.py</code> (numpy/scipy/soundfile).
  </footer>
</div></body></html>'''
        out = os.path.join(folder, "index.html")
        open(out, "w", encoding="utf-8").write(page)
        print("wrote", out)

def write_hub():
    data = load_data()
    cards = []
    for st in data:
        cards.append(f'''
    <a class="card" href="{esc(st['folder'])}/index.html">
      <img src="{esc(st['folder'])}/cover.svg" alt="{esc(st['name'])}">
      <div class="cname">{esc(st['name'])}</div>
      <div class="czh">{esc(st['zh'])}</div>
      <div class="ctag">{esc(st['tagline'])}</div>
      <div class="clufs">{len(st['tracks'])} tracks · ~{st['target_lufs']} LUFS</div>
    </a>''')
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(ALBUM_TITLE)} — {esc(SERIES)}</title>
<style>{BASE_CSS}</style></head>
<body><div class="wrap">
  <header>
    <h1>{esc(ALBUM_TITLE)}</h1>
    <div class="tag">THE MIX ENGINEER SERIES</div>
    <img class="cover" src="cover.svg" alt="cover">
    <p class="intro">Six instrumental tracks, {len(data)} mixing engineers. Same stems, same
    arrangement — only the mix philosophy changes: balance, EQ, compression, reverb, width and
    loudness follow each mixer's documented signature. Pick a mixer to listen and read their chain.</p>
  </header>
  <div class="grid">{''.join(cards)}</div>
  <footer>
    Instrumental R&amp;B/soul assembled from the musickit sample library.<br>
    Full documentation (references, chain tables, stem lists): <a href="ALBUM_NOTES.md">ALBUM_NOTES.md</a>.<br>
    Generated with <code>build_album.py</code> + <code>generate_album_docs.py</code>.
  </footer>
</div></body></html>'''
    open(OUT_HTML, "w", encoding="utf-8").write(page)
    print("wrote", OUT_HTML)

def write_channels():
    """L1 频道目录: 把 24 位混音师风格输出为频道元数据 JSON(Mubert 频道形态对齐)。"""
    data = load_data()
    channels = []
    for st in data:
        channels.append({
            "slug": st["slug"],
            "name": st["name"],
            "zh": st["zh"],
            "color": st["color"],
            "tagline": st["tagline"],
            "about": st["about"],
            "refs": st["refs"],
            "target_lufs": st["target_lufs"],
            "page": st["folder"] + "/index.html",
            "cover": st["folder"] + "/cover.svg",
            "sig": st["sig"],
            "impl": st["impl"],
            "tracks": [{"num": t["num"], "title": t["title"], "tempo": t["tempo"],
                        "key": t["key"], "dur": t["dur"], "lufs": t["lufs"],
                        "out": t["out"]} for t in st["tracks"]],
        })
    with open(os.path.join(ALBUM, "channels.json"), "w", encoding="utf-8") as f:
        json.dump({"channels": channels}, f, ensure_ascii=False, indent=2)
    print("wrote", os.path.join(ALBUM, "channels.json"))


if __name__ == "__main__":
    write_markdown()
    open(OUT_COVER, "w", encoding="utf-8").write(series_cover())
    print("wrote", OUT_COVER)
    write_style_pages()
    write_hub()
    write_channels()
    print("docs done")
