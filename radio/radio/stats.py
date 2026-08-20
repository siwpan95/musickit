"""E4 听众历史统计：SQLite 记录连接事件 + 聚合查询。

- init() 建库建表（WAL 模式，并发安全）
- log_connect(ip,ua) / log_disconnect(ip,ua,duration) 记录事件
- listener_stats(hours=24) 聚合：24h 连接曲线 / 峰值 / Top IP / 热门时段

D4 的内存环只保留最近 100 条；E4 持久化到 radio.db，面板出历史图表。
"""
import os
import sqlite3
import threading
import time
import datetime
from collections import Counter

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_PROJECT_DIR, "radio.db")

_lock = threading.Lock()
_conn = None


def init():
    """建库建表。幂等。"""
    global _conn
    if _conn is not None:
        return
    _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("""CREATE TABLE IF NOT EXISTS listener_events (
        ts INTEGER NOT NULL,
        ip TEXT,
        ua TEXT,
        duration INTEGER DEFAULT 0,
        action TEXT NOT NULL
    )""")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON listener_events(ts)")
    _conn.commit()


def log_connect(ip, ua):
    if _conn is None:
        return
    try:
        with _lock:
            _conn.execute(
                "INSERT INTO listener_events (ts, ip, ua, duration, action) VALUES (?,?,?,?,?)",
                (int(time.time()), ip or "", ua or "", 0, "connect"))
            _conn.commit()
    except Exception:
        pass


def log_disconnect(ip, ua, duration):
    if _conn is None:
        return
    try:
        with _lock:
            _conn.execute(
                "INSERT INTO listener_events (ts, ip, ua, duration, action) VALUES (?,?,?,?,?)",
                (int(time.time()), ip or "", ua or "", int(duration), "disconnect"))
            _conn.commit()
    except Exception:
        pass


def listener_stats(hours=24):
    """聚合最近 hours 小时的听众统计。"""
    if _conn is None:
        return {"hours": hours, "curve": [], "peak": 0, "total": 0, "top_ips": [], "top_hours": []}
    cutoff = int(time.time()) - hours * 3600
    with _lock:
        rows = _conn.execute(
            "SELECT ts, ip, ua, duration, action FROM listener_events WHERE ts >= ?",
            (cutoff,)).fetchall()
    curve = [0] * hours
    connects = [r for r in rows if r[4] == "connect"]
    for ts, ip, ua, dur, act in connects:
        h = (ts - cutoff) // 3600
        if 0 <= h < hours:
            curve[h] += 1
    peak = max(curve) if curve else 0
    ip_counter = Counter((r[1] or "?") for r in connects)
    top_ips = [{"ip": ip, "count": c} for ip, c in ip_counter.most_common(5)]
    hour_counter = Counter()
    for ts, ip, ua, dur, act in connects:
        h = datetime.datetime.fromtimestamp(ts).hour
        hour_counter[h] += 1
    top_hours = [{"hour": h, "count": c} for h, c in hour_counter.most_common(5)]
    total_duration = sum(r[3] for r in rows if r[4] == "disconnect")
    return {
        "hours": hours,
        "curve": curve,
        "peak": peak,
        "total_connects": len(connects),
        "total_duration_sec": total_duration,
        "top_ips": top_ips,
        "top_hours": top_hours,
    }
