"""Perhitungan progres, jadwal, dan kesehatan proyek."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import db
from core.timeutil import today

HEALTH_ORDER = ["Terlambat", "Berisiko", "Aman", "Selesai"]

ENRICH_COLUMNS = ["progress_eff", "days_left", "expected", "gap", "health", "health_reason"]


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom turunan: progres efektif, sisa hari, progres ideal, kesehatan."""
    if df.empty:
        out = df.copy()
        for c in ENRICH_COLUMNS:
            out[c] = pd.Series(dtype="object")
        return out

    out = df.copy()
    t = pd.Timestamp(today())
    start = pd.to_datetime(out["start_date"], errors="coerce")
    due = pd.to_datetime(out["due_date"], errors="coerce")

    auto = (out["progress_mode"] == "auto") & (out["tasks_total"] > 0)
    task_pct = (out["tasks_done"] / out["tasks_total"].replace(0, np.nan) * 100).round()
    prog = np.where(auto, task_pct, out["progress"])
    out["progress_eff"] = pd.Series(prog, index=out.index).fillna(0).clip(0, 100).astype(int)
    out.loc[out["status"] == "Selesai", "progress_eff"] = 100

    out["days_left"] = (due - t).dt.days
    span = (due - start).dt.days
    elapsed = (t - start).dt.days
    expected = (elapsed / span.where(span > 0) * 100).clip(0, 100)
    out["expected"] = expected.round()
    out["gap"] = out["expected"] - out["progress_eff"]

    res = out.apply(_health, axis=1, result_type="expand")
    out["health"] = res[0]
    out["health_reason"] = res[1]
    out["group_name"] = out["group_name"].fillna("Tanpa grup")
    out["group_color"] = out["group_color"].fillna("#94A3B8")
    return out


def _health(row) -> tuple[str, str]:
    if row["status"] == "Selesai":
        return "Selesai", "Proyek selesai"
    reasons = []
    days_left = row["days_left"]
    if pd.notna(days_left) and days_left < 0:
        return "Terlambat", f"Lewat tenggat {int(abs(days_left))} hari"
    if row.get("blockers_high", 0) > 0:
        reasons.append(f"{int(row['blockers_high'])} hambatan prioritas tinggi")
    if pd.notna(row["gap"]) and row["gap"] > 20 and row["status"] not in ("Ide", "Tertunda"):
        reasons.append(f"Progres tertinggal {int(row['gap'])} poin dari jadwal")
    if pd.notna(days_left) and days_left <= 3 and row["progress_eff"] < 80:
        reasons.append("Tenggat dekat, progres di bawah 80%")
    if reasons:
        return "Berisiko", "; ".join(reasons)
    return "Aman", "Sesuai jadwal"


def load_projects(include_archived: bool = False) -> pd.DataFrame:
    return enrich(db.list_projects(include_archived=include_archived))


def summary(df: pd.DataFrame) -> dict:
    """Angka ringkas untuk KPI dashboard."""
    if df.empty:
        return dict(total=0, active=0, ideas=0, paused=0, done=0, done_30=0, avg_progress=0,
                    late=0, risk=0, blockers=0, blockers_high=0, due_7=0, groups=0)
    open_ = df[df["status"] != "Selesai"]
    active = df[df["status"].isin(db.ACTIVE_STATUSES)]
    done = df[df["status"] == "Selesai"]
    completed = pd.to_datetime(done["completed_at"], errors="coerce")
    done_30 = int((completed >= pd.Timestamp(today()) - pd.Timedelta(days=30)).sum())
    due_7 = int(((open_["days_left"] >= 0) & (open_["days_left"] <= 7)).sum())
    return dict(
        total=len(df),
        active=len(active),
        ideas=int((df["status"] == "Ide").sum()),
        paused=int((df["status"] == "Tertunda").sum()),
        done=len(done),
        done_30=done_30,
        avg_progress=int(round(active["progress_eff"].mean())) if len(active) else 0,
        late=int((open_["health"] == "Terlambat").sum()),
        risk=int((open_["health"] == "Berisiko").sum()),
        blockers=int(open_["blockers_open"].sum()),
        blockers_high=int(open_["blockers_high"].sum()),
        due_7=due_7,
        groups=df["group_name"].nunique(),
    )


def narrative(s: dict) -> str:
    """Kalimat ringkasan otomatis untuk bagian atas dashboard."""
    if s["total"] == 0:
        return "Belum ada proyek. Tambahkan proyek pertama lewat tombol Proyek baru di sidebar."
    parts = [f"Ada <b>{s['active']} proyek aktif</b> dari {s['groups']} grup dengan rata-rata progres <b>{s['avg_progress']}%</b>."]
    attention = s["late"] + s["risk"]
    if attention:
        detail = []
        if s["late"]:
            detail.append(f"{s['late']} terlambat")
        if s["risk"]:
            detail.append(f"{s['risk']} berisiko")
        parts.append(f"<b>{attention} proyek perlu perhatian</b> ({', '.join(detail)}).")
    else:
        parts.append("Semua proyek terbuka berjalan sesuai jadwal.")
    if s["blockers"]:
        parts.append(f"{s['blockers']} hambatan masih terbuka.")
    if s["due_7"]:
        parts.append(f"{s['due_7']} tenggat jatuh dalam 7 hari ke depan.")
    return " ".join(parts)


def by_group(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["group_name", "group_color", "total", "open", "done", "avg_progress",
                                     "late", "risk", "blockers"])
    rows = []
    for (name, color), g in df.groupby(["group_name", "group_color"], dropna=False):
        open_ = g[g["status"] != "Selesai"]
        rows.append(dict(
            group_name=name, group_color=color, total=len(g), open=len(open_),
            done=int((g["status"] == "Selesai").sum()),
            avg_progress=int(round(open_["progress_eff"].mean())) if len(open_) else 100,
            late=int((open_["health"] == "Terlambat").sum()),
            risk=int((open_["health"] == "Berisiko").sum()),
            blockers=int(open_["blockers_open"].sum()),
        ))
    return pd.DataFrame(rows).sort_values(["open", "total"], ascending=False).reset_index(drop=True)
