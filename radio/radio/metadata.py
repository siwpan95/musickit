"""本地歌曲标签 + 内嵌封面提取（纯 mutagen，不访问任何外部网络）。

- get_meta(path)  -> {"title","artist","album"}（拿不到字段为 None）
- get_cover(path) -> (bytes, mime) 或 None

结果按 path 缓存，重复请求不重算。
"""
import os
import json
import hashlib
import threading
import urllib.parse
import urllib.request

try:
    from mutagen import File as MutagenFile
    _HAVE = True
except Exception:
    _HAVE = False

_meta_cache = {}
_cover_cache = {}
_lock = threading.Lock()


def available():
    return _HAVE


def get_meta(path):
    if not _HAVE or not path or not os.path.isfile(path):
        return {"title": None, "artist": None, "album": None}
    with _lock:
        if path in _meta_cache:
            return _meta_cache[path]
    meta = {"title": None, "artist": None, "album": None}
    try:
        audio = MutagenFile(path, easy=True)
        tags = audio.tags if audio else None
        if tags:
            def g(k):
                v = tags.get(k)
                return v[0] if isinstance(v, list) and v else None
            meta = {"title": g("title"), "artist": g("artist"), "album": g("album")}
    except Exception:
        pass
    with _lock:
        _meta_cache[path] = meta
    return meta


def get_cover(path):
    if not _HAVE or not path or not os.path.isfile(path):
        return None
    with _lock:
        if path in _cover_cache:
            return _cover_cache[path]
    result = None
    try:
        audio = MutagenFile(path)
        if audio is not None:
            cls = audio.__class__.__name__
            if cls == "MP3" and audio.tags:
                apics = audio.tags.getall("APIC")
                if apics:
                    result = (apics[0].data, apics[0].mime or "image/jpeg")
            elif cls == "FLAC":
                if audio.pictures:
                    pic = audio.pictures[0]
                    result = (pic.data, pic.mime or "image/png")
            elif cls in ("MP4", "M4A") and audio.tags:
                covr = audio.tags.get("covr")
                if covr:
                    data = bytes(covr[0])
                    fmt = getattr(covr[0], "imageformat", 0x0D)
                    mime = "image/png" if fmt == 0x0E else "image/jpeg"
                    result = (data, mime)
            elif cls.startswith("Ogg") or cls in ("OggOpus", "OggVorbis", "OggFlac"):
                pics = getattr(audio, "pictures", None) or []
                if pics:
                    result = (pics[0].data, pics[0].mime or "image/png")
    except Exception:
        result = None
    with _lock:
        _cover_cache[path] = result
    return result


# ---------- E3：在线封面补全（iTunes Search API，零密钥）----------

_COVERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "covers")
_online_cache = {}        # path -> (bytes, mime) 或 None，避免重复查在线


def _itunes_search(artist, title):
    """查 iTunes Search API，返回 artwork URL 或 None。零密钥。"""
    term = ((artist or "") + " " + (title or "")).strip()
    if not term:
        return None
    url = ("https://itunes.apple.com/search?term=" +
           urllib.parse.quote(term) + "&entity=song&limit=1")
    try:
        r = urllib.request.urlopen(url, timeout=5)
        data = json.loads(r.read().decode("utf-8", "replace"))
        results = data.get("results", [])
        if results:
            art = results[0].get("artworkUrl100")
            if art:
                # 升级到 600x600（iTunes URL 支持尺寸替换）
                return art.replace("100x100bb", "600x600bb")
    except Exception:
        return None
    return None


def _download_cover(url):
    try:
        r = urllib.request.urlopen(url, timeout=5)
        return (r.read(), "image/jpeg")
    except Exception:
        return None


def get_cover_online(artist, title):
    """在线查 iTunes 封面，缓存到 covers/。返回 (bytes, mime) 或 None。"""
    key = hashlib.md5(((artist or "") + "|" + (title or "")).encode("utf-8")).hexdigest()
    cache_file = os.path.join(_COVERS_DIR, key + ".jpg")
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, "rb") as f:
                return (f.read(), "image/jpeg")
        except Exception:
            pass
    art_url = _itunes_search(artist, title)
    if not art_url:
        return None
    cov = _download_cover(art_url)
    if not cov:
        return None
    try:
        os.makedirs(_COVERS_DIR, exist_ok=True)
        with open(cache_file, "wb") as f:
            f.write(cov[0])
    except Exception:
        pass
    return cov


def get_cover_smart(path):
    """本地内嵌封面优先；无则查 iTunes（E3，零密钥）。结果按 path 缓存。"""
    local = get_cover(path)
    if local:
        return local
    with _lock:
        if path in _online_cache:
            return _online_cache[path]
    meta = get_meta(path)
    artist, title = meta.get("artist"), meta.get("title")
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    result = get_cover_online(artist, title)
    with _lock:
        _online_cache[path] = result
    return result
