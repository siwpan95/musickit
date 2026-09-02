"""C3 社群同步：把“正在播放”发布到 Discord(webhook) 与 Telegram(Bot API)。

凭据放在项目根 integrations.json（不提交密钥）：
  {"enabled": false, "discord_webhook": "", "telegram_token": "", "telegram_chat_id": ""}

- maybe_announce(path, title, mode): 仅当 enabled 且有凭据才后台发布（曲目切换时自动调用）
- announce_now(title, artist, cover_path, mode): 立刻发一次（扩展“立即发布”按钮用）
- status()/save(): 供 /api/integrations 读取与保存（不泄露密钥）
"""
import os
import json
import threading
import urllib.parse

try:
    import requests
    _HAVE_REQ = True
except Exception:
    _HAVE_REQ = False

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG_PATH = os.path.join(_ROOT, "integrations.json")
_PUBLIC_URL_PATH = os.path.join(_ROOT, "public_url.txt")

DEFAULT_CFG = {
    "enabled": False,
    "discord_webhook": "",
    "telegram_token": "",
    "telegram_chat_id": "",
}


def _read_cfg():
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return {**DEFAULT_CFG, **d}
    except Exception:
        pass
    return dict(DEFAULT_CFG)


def _write_cfg(cfg):
    tmp = _CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CFG_PATH)


def _read_public_url():
    try:
        with open(_PUBLIC_URL_PATH, encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def _cover_url(cover_path, mode):
    """封面仅在 playlist 模式且有公网地址时才有意义（Discord/Telegram 需可达 URL）。"""
    if mode != "playlist" or not cover_path:
        return None
    base = _read_public_url()
    if not base:
        return None
    return base.rstrip("/") + "/api/cover?path=" + urllib.parse.quote(cover_path)


def status():
    """返回启用状态（不泄露密钥，只给布尔）。"""
    cfg = _read_cfg()
    return {
        "enabled": bool(cfg.get("enabled")),
        "discord": bool(cfg.get("discord_webhook")),
        "telegram": bool(cfg.get("telegram_token") and cfg.get("telegram_chat_id")),
    }


def save(cfg):
    """原子写配置，返回最新状态。"""
    clean = {
        "enabled": bool(cfg.get("enabled")),
        "discord_webhook": (cfg.get("discord_webhook") or "").strip(),
        "telegram_token": (cfg.get("telegram_token") or "").strip(),
        "telegram_chat_id": (cfg.get("telegram_chat_id") or "").strip(),
    }
    _write_cfg(clean)
    return status()


def maybe_announce(path=None, title=None, mode="playlist"):
    """曲目切换时自动调用：enabled 且有任一凭据才后台发布。"""
    cfg = _read_cfg()
    if not cfg.get("enabled"):
        return
    if not (cfg.get("discord_webhook") or
            (cfg.get("telegram_token") and cfg.get("telegram_chat_id"))):
        return
    artist = _derive_artist(path, title, mode)
    threading.Thread(target=_announce, args=(title, artist, path, mode),
                     daemon=True).start()


def announce_now(title, artist=None, cover_path=None, mode="playlist"):
    """手动立即发布（扩展按钮）。凭据不齐返回 False。"""
    cfg = _read_cfg()
    if not (cfg.get("discord_webhook") or
            (cfg.get("telegram_token") and cfg.get("telegram_chat_id"))):
        return False
    threading.Thread(target=_announce, args=(title, artist, cover_path, mode),
                     daemon=True).start()
    return True


def _derive_artist(path, title, mode):
    if mode == "playlist" and path:
        try:
            from . import metadata
            return metadata.get_meta(path).get("artist")
        except Exception:
            return None
    return None


def _announce(title, artist, cover_path, mode):
    if not _HAVE_REQ:
        return
    cfg = _read_cfg()
    if artist and title:
        caption = f"\U0001f3b6 {artist} — {title}"
    elif title:
        caption = f"\U0001f3b6 {title}"
    else:
        caption = "\U0001f3b6 正在播放"
    cover = _cover_url(cover_path, mode)

    wh = cfg.get("discord_webhook")
    if wh:
        _to_discord(wh, caption, cover, title, artist)
    tk = cfg.get("telegram_token")
    cid = cfg.get("telegram_chat_id")
    if tk and cid:
        _to_telegram(tk, cid, caption, cover)


def _to_discord(webhook, caption, cover, title, artist):
    try:
        embed = {
            "title": title or "正在播放",
            "description": artist or "",
            "color": 0x9B5CFF,
            "footer": {"text": "My Python Radio"},
        }
        if cover:
            embed["image"] = {"url": cover}
        requests.post(webhook, json={"content": caption, "embeds": [embed]},
                      timeout=8)
    except Exception:
        pass


def _to_telegram(token, chat_id, caption, cover):
    try:
        base = f"https://api.telegram.org/bot{token}"
        if cover:
            # Telegram 可直接吃 https 图片 URL
            requests.post(f"{base}/sendPhoto",
                          data={"chat_id": chat_id, "photo": cover, "caption": caption},
                          timeout=10)
        else:
            requests.post(f"{base}/sendMessage",
                          data={"chat_id": chat_id, "text": caption}, timeout=8)
    except Exception:
        pass
