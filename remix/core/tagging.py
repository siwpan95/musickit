"""tagging — 把提示词/配方写进成品文件的元数据（架构文档 §7.3 的 `sentence` 项）。

为什么需要：提示词里最像「AI 提示词」的字段是 `sentence`（整句自然语言），
但它此前只被打印，成品里没有任何痕迹 —— 事后无法回答「这首是用什么提示词做的」。
写进 ID3 comment 是最低成本的可追溯方案：不占音频、任何播放器可读、不依赖数据库。

覆盖格式：mp3 / flac / ogg（走 easy 接口）、wav（走 ID3，mutagen.wave）。
写失败不抛错（打标签不该让渲染失败），返回结构化结果供调用方记录。
"""
from __future__ import annotations

import os
from typing import Any

#: 写入的字段上限（避免超长提示词把 ID3 撑爆/截断乱码）
MAX_LEN = 900


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    s = str(text).strip()
    return (s[:MAX_LEN] + "…") if len(s) > MAX_LEN else s


def _write_easy(path: str, fields: dict[str, str]) -> list[str]:
    from mutagen import File as MFile

    audio = MFile(path, easy=True)
    if audio is None:
        return []
    if audio.tags is None:
        audio.add_tags()
    written = []
    for key, value in fields.items():
        if value is None:
            continue
        audio[key] = [value]
        written.append(key)
    audio.save()
    return written


def _write_wave_id3(path: str, fields: dict[str, str]) -> list[str]:
    """WAV 走 ID3（mutagen.wave.WAVE），字段名用 ID3 frame。"""
    from mutagen.id3 import TALB, TCOM, TIT2, TPE1, COMM
    from mutagen.wave import WAVE

    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    written: list[str] = []
    mapping = {
        "title": lambda v: tags.add(TIT2(encoding=3, text=v)),
        "artist": lambda v: tags.add(TPE1(encoding=3, text=v)),
        "album": lambda v: tags.add(TALB(encoding=3, text=v)),
        "composer": lambda v: tags.add(TCOM(encoding=3, text=v)),
        "comment": lambda v: tags.add(COMM(encoding=3, lang="eng", desc="", text=v)),
    }
    for key, value in fields.items():
        fn = mapping.get(key)
        if fn is None or value is None:
            continue
        fn(value)
        written.append(key)
    audio.save()
    return written


def write_tags(
    path: str,
    *,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    composer: str | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """把字段写进音频文件；返回 {ok, written, error}。

    失败只记录不抛：元数据是附加价值，不该让渲染整体失败。
    """
    fields = {k: _clip(v) for k, v in {
        "title": title, "artist": artist, "album": album,
        "composer": composer, "comment": comment,
    }.items() if _clip(v)}
    if not fields or not os.path.isfile(path):
        return {"ok": False, "written": [], "error": "no fields or missing file"}

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".wav":
            written = _write_wave_id3(path, fields)
        else:
            written = _write_easy(path, fields)
        return {"ok": bool(written), "written": written, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "written": [], "error": f"{type(e).__name__}: {e}"}


def read_tags(path: str) -> dict[str, Any]:
    """读回元数据（用于验证/测试）。

    WAV 必须走 ID3 帧读取：mutagen 的 easy 接口不把 ID3 的 COMM 映射成 "comment"，
    用 easy 读 WAV 会拿到空字典（这是实测踩到的坑）。
    """
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".wav":
            from mutagen.wave import WAVE

            audio = WAVE(path)
            if audio.tags is None:
                return {}
            tags = audio.tags
            out: dict[str, Any] = {}
            for frame, key in (("TIT2", "title"), ("TPE1", "artist"),
                               ("TALB", "album"), ("TCOM", "composer")):
                if frame in tags:
                    out[key] = str(tags[frame])
            for k in tags.keys():
                if str(k).startswith("COMM"):
                    out["comment"] = str(tags[k])
                    break
            return out

        from mutagen import File as MFile

        audio = MFile(path, easy=True)
        if audio is None or audio.tags is None:
            return {}
        out = {}
        for key in ("title", "artist", "album", "composer", "comment"):
            try:
                v = audio.get(key)
            except Exception:  # noqa: BLE001
                v = None
            if v:
                out[key] = v[0] if isinstance(v, list) else v
        return out
    except Exception:  # noqa: BLE001
        return {}
