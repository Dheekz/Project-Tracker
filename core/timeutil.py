"""Utilitas waktu dengan zona waktu tetap (default Asia/Jakarta).

Server cloud biasanya berjalan dalam UTC. Tanpa zona waktu tetap,
perhitungan "hari ini" dan "terlambat" bisa meleset hingga 7 jam.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TRACKER_TZ", "Asia/Jakarta"))

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                 "Agustus", "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def now() -> datetime:
    return datetime.now(TZ)


def now_str() -> str:
    return now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> date:
    return now().date()


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        import pandas as pd
        if pd.isna(value):
            return None
        return pd.to_datetime(value).date()
    except Exception:
        return None


def fmt_date(value, long: bool = False) -> str:
    d = parse_date(value)
    if not d:
        return "-"
    if long:
        return f"{d.day} {BULAN_PANJANG[d.month - 1]} {d.year}"
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def fmt_day_long(d: date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN_PANJANG[d.month - 1]} {d.year}"


def fmt_ts(value) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)
    return f"{dt.day} {BULAN[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def relative_ts(value) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)
    delta = now().replace(tzinfo=None) - dt
    s = int(delta.total_seconds())
    if s < 60:
        return "baru saja"
    if s < 3600:
        return f"{s // 60} menit lalu"
    if s < 86400:
        return f"{s // 3600} jam lalu"
    if s < 86400 * 30:
        return f"{s // 86400} hari lalu"
    return fmt_date(dt)


def days_label(days_left) -> str:
    try:
        n = int(days_left)
    except (TypeError, ValueError):
        return "Tanpa tenggat"
    if n < 0:
        return f"Lewat {abs(n)} hari"
    if n == 0:
        return "Hari ini"
    if n == 1:
        return "Besok"
    return f"{n} hari lagi"
