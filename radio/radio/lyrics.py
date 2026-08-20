"""C2 歌词：本地 LRC（零密钥离线）+ LRCLIB 在线（keyless）。

- local_lyrics(path)   找同目录同名 .lrc，解析成 [{"t":秒, "text":...}]
- online_lyrics(title, artist)  查 LRCLIB（无需 API key），返回同步/纯文本
- get_lyrics(path, title, artist)  先本地后在线

返回结构：
  {"source": "local"|"lrclib"|None, "synced": bool,
   "lines": [{"t":float,"text":str}], "plain": str}
"""
import os
import re

try:
    import requests
    _HAVE_REQ = True
except Exception:
    _HAVE_REQ = False

_LRCLIB = "https://lrclib.net/api/get"
_LRC_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _parse_lrc(text):
    """把 LRC 文本解析成 [(秒, 行), ...] 按时间升序。支持一行多时间戳。"""
    out = []
    for line in (text or "").splitlines():
        if not _LRC_RE.search(line):
            continue
        content = line[line.rfind("]") + 1:].strip()
        if not content:
            continue
        for tm in _LRC_RE.finditer(line):
            mm = int(tm.group(1))
            ss = int(tm.group(2))
            frac = (tm.group(3) or "0").ljust(3, "0")[:3]
            t = mm * 60 + ss + int(frac) / 1000.0
            out.append((round(t, 3), content))
    out.sort(key=lambda x: x[0])
    return out


def local_lyrics(path):
    """同目录同名的 .lrc；没有则返回 None。"""
    if not path or not os.path.isfile(path):
        return None
    lrc = os.path.splitext(path)[0] + ".lrc"
    if not os.path.isfile(lrc):
        return None
    try:
        with open(lrc, encoding="utf-8") as f:
            data = f.read()
    except Exception:
        return None
    lines = _parse_lrc(data)
    if lines:
        return {
            "source": "local",
            "synced": True,
            "lines": [{"t": t, "text": x} for t, x in lines],
            "plain": "\n".join(x for _, x in lines),
        }
    # 无时间戳的纯文本歌词
    plain = "\n".join(l.strip() for l in data.splitlines() if l.strip())
    return {"source": "local", "synced": False, "lines": [], "plain": plain}


def online_lyrics(title, artist):
    """LRCLIB keyless 查询；失败/无结果返回 None。"""
    if not _HAVE_REQ or not (title or artist):
        return None
    params = {}
    if artist:
        params["artist"] = artist
    if title:
        params["title"] = title
    try:
        r = requests.get(
            _LRCLIB, params=params, timeout=6,
            headers={"User-Agent": "pyradio/1.0"},
        )
        if r.status_code != 200:
            return None
        j = r.json()
        synced = j.get("syncedLyrics") or ""
        plain = j.get("plainLyrics") or ""
        if synced:
            lines = _parse_lrc(synced)
            if lines:
                return {
                    "source": "lrclib",
                    "synced": True,
                    "lines": [{"t": t, "text": x} for t, x in lines],
                    "plain": plain,
                }
        if plain:
            return {"source": "lrclib", "synced": False, "lines": [], "plain": plain}
    except Exception:
        return None
    return None


def get_lyrics(path=None, title=None, artist=None):
    loc = local_lyrics(path)
    if loc:
        return loc
    on = online_lyrics(title, artist)
    if on:
        return on
    return {"source": None, "synced": False, "lines": [], "plain": ""}
