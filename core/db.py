"""Lapisan data aplikasi di atas backend (Google Sheets atau SQLite).

Semua fungsi publik di sini dipakai oleh halaman-halaman di folder views/.
Data dibaca sekali per siklus cache (lihat store.read_cached), lalu diolah
dengan pandas. Setiap penulisan langsung menghapus cache.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from core import store as _store
from core.schema import (  # noqa: F401  (diekspor ulang untuk views)
    ACTIVE_STATUSES, BLOCKER_SEVERITIES, BLOCKER_STATUSES, FILE_TYPES, GROUP_KINDS, PRIORITIES,
    REQ_CATEGORIES, REQ_STATUSES, STATUSES, TABLE_ORDER, TABLES,
)
from core.timeutil import now_str, today

CHILD_COLUMNS = {
    "tasks": ["title", "done", "due_date", "sort"],
    "requirements": ["item", "category", "status", "notes"],
    "blockers": ["description", "severity", "status", "raised_at", "resolved_at", "resolution"],
    "files": ["name", "url", "ftype", "notes", "added_at"],
}
CHILD_TABLES = list(CHILD_COLUMNS) + ["activity"]

PROJECT_FIELDS = [
    "group_id", "name", "description", "status", "priority", "progress", "progress_mode",
    "start_date", "due_date", "main_link", "tags", "role", "stakeholder", "next_action",
    "pinned", "archived",
]


# ---------------------------------------------------------------------------
# Akses dasar
# ---------------------------------------------------------------------------
def backend():
    return _store.get_store()


def backend_info() -> dict:
    return backend().info()


def refresh() -> None:
    """Paksa baca ulang dari sumber (misalnya setelah edit manual di Google Sheet)."""
    _store.invalidate()


def _tables() -> dict[str, pd.DataFrame]:
    return _store.read_cached()


def _t(name: str) -> pd.DataFrame:
    return _tables()[name]


def _written() -> None:
    _store.invalidate()


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else (int(v) if float(v).is_integer() else float(v))
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def init_db(seed_if_new: bool = True) -> None:
    meta = _t("meta")
    if "initialized" in meta["key"].tolist():
        return
    if seed_if_new and _t("projects").empty and _t("groups").empty:
        seed_sample()
    set_meta("initialized", now_str())


def get_meta(key: str) -> str | None:
    m = _t("meta")
    hit = m[m["key"] == key]
    return None if hit.empty else hit.iloc[0]["value"]


def set_meta(key: str, value: str) -> None:
    m = _t("meta")
    hit = m[m["key"] == key]
    if hit.empty:
        backend().insert("meta", [{"key": key, "value": value}])
    else:
        backend().update_many("meta", {int(hit.iloc[0]["id"]): {"value": value}})
    _written()


# ---------------------------------------------------------------------------
# Grup / sumber proyek
# ---------------------------------------------------------------------------
def list_groups() -> pd.DataFrame:
    g = _t("groups").sort_values(["sort", "name"]).reset_index(drop=True)
    p = _t("projects")
    counts = p[p["archived"] == 0].groupby("group_id").size()
    g["project_count"] = g["id"].astype(float).map(counts).fillna(0).astype(int)
    return g


def create_group(name: str, kind: str, color: str, description: str = "") -> int:
    g = _t("groups")
    nxt = int(g["sort"].max()) + 1 if len(g) else 1
    gid = backend().insert("groups", [dict(name=name.strip(), kind=kind, color=color,
                                           description=description.strip(), sort=nxt, created_at=now_str())])[0]
    _written()
    return gid


def update_group(gid: int, name: str, kind: str, color: str, description: str) -> None:
    backend().update_many("groups", {int(gid): dict(name=name.strip(), kind=kind, color=color,
                                                   description=description.strip())})
    _written()


def delete_group(gid: int, move_to: int | None = None) -> None:
    p = _t("projects")
    moving = p[p["group_id"] == gid]["id"].tolist()
    if moving:
        backend().update_many("projects", {int(pid): {"group_id": move_to} for pid in moving})
    backend().delete_many({"groups": [int(gid)]})
    _written()


# ---------------------------------------------------------------------------
# Proyek
# ---------------------------------------------------------------------------
def _count(df: pd.DataFrame) -> pd.Series:
    return df.groupby("project_id").size()


def list_projects(include_archived: bool = False) -> pd.DataFrame:
    tb = _tables()
    p = tb["projects"].copy()
    if not include_archived:
        p = p[p["archived"] == 0]
    g = tb["groups"][["id", "name", "color", "kind"]].rename(
        columns={"id": "group_id", "name": "group_name", "color": "group_color", "kind": "group_kind"})
    g["group_id"] = g["group_id"].astype(float)
    p = p.merge(g, on="group_id", how="left")

    t, b, r, f, a = tb["tasks"], tb["blockers"], tb["requirements"], tb["files"], tb["activity"]
    open_b = b[b["status"] == "Terbuka"]
    stats = {
        "tasks_total": _count(t),
        "tasks_done": _count(t[t["done"] == 1]),
        "blockers_open": _count(open_b),
        "blockers_high": _count(open_b[open_b["severity"].isin(["Tinggi", "Kritis"])]),
        "req_total": _count(r),
        "req_done": _count(r[r["status"] == "Terpenuhi"]),
        "files_total": _count(f),
    }
    for col, series in stats.items():
        p[col] = p["id"].map(series).fillna(0).astype(int)
    last = a.dropna(subset=["project_id"]).groupby("project_id")["ts"].max()
    last.index = last.index.astype(int)
    p["last_activity"] = p["id"].map(last)
    p["_upd"] = pd.to_datetime(p["updated_at"], errors="coerce")
    p = p.sort_values(["pinned", "_upd"], ascending=[False, False], na_position="last").drop(columns="_upd")
    return p.reset_index(drop=True)


def get_project(pid: int) -> dict | None:
    p = list_projects(include_archived=True)
    hit = p[p["id"] == int(pid)]
    return None if hit.empty else {k: _clean(v) for k, v in hit.iloc[0].to_dict().items()}


def _project_record(data: dict) -> dict:
    ts = now_str()
    rec = {k: data.get(k) for k in PROJECT_FIELDS if k in data}
    rec.setdefault("status", "To Do")
    rec.setdefault("priority", "Sedang")
    rec.setdefault("progress", 0)
    rec.setdefault("progress_mode", "manual")
    rec["created_at"] = ts
    rec["updated_at"] = ts
    if rec.get("status") == "Selesai":
        rec["completed_at"] = ts
        rec["progress"] = 100
    return rec


def create_project(data: dict) -> int:
    rec = _project_record(data)
    pid = backend().insert("projects", [rec])[0]
    backend().insert("activity", [dict(project_id=pid, ts=now_str(), kind="dibuat",
                                       message=f"Proyek dibuat dengan status {rec['status']}")])
    _written()
    return pid


def update_project(pid: int, data: dict, log: bool = True) -> None:
    old = get_project(pid)
    if not old:
        return
    payload = {k: v for k, v in data.items() if k in PROJECT_FIELDS}
    if not payload:
        return
    new_status = payload.get("status", old["status"])
    if new_status == "Selesai" and old["status"] != "Selesai":
        payload["completed_at"] = now_str()
        if payload.get("progress_mode", old["progress_mode"]) == "manual":
            payload["progress"] = 100
    elif new_status != "Selesai" and old["status"] == "Selesai":
        payload["completed_at"] = None
    payload["updated_at"] = now_str()
    backend().update_many("projects", {int(pid): payload})

    msgs = []
    if log:
        if "status" in data and data["status"] != old["status"]:
            msgs.append(("status", f"Status berubah: {old['status']} ke {data['status']}"))
        if data.get("progress") is not None and int(data["progress"]) != int(old["progress"] or 0) \
                and payload.get("progress_mode", old["progress_mode"]) == "manual":
            msgs.append(("progres", f"Progres diperbarui: {old['progress']}% ke {int(data['progress'])}%"))
        if "due_date" in data and (data["due_date"] or None) != (old["due_date"] or None):
            msgs.append(("tenggat", f"Tenggat diubah ke {data['due_date'] or 'tanpa tenggat'}"))
    if msgs:
        ts = now_str()
        backend().insert("activity", [dict(project_id=pid, ts=ts, kind=k, message=m) for k, m in msgs])
    _written()


def set_status(pid: int, status: str) -> None:
    update_project(pid, {"status": status})


def delete_project(pid: int) -> None:
    tb = _tables()
    spec = {"projects": [int(pid)]}
    for t in CHILD_TABLES:
        df = tb[t]
        spec[t] = df[df["project_id"] == int(pid)]["id"].astype(int).tolist()
    backend().delete_many(spec)
    _written()


def touch_project(pid: int) -> None:
    backend().update_many("projects", {int(pid): {"updated_at": now_str()}})
    _written()


# ---------------------------------------------------------------------------
# Data turunan: tugas, kebutuhan, hambatan, file kerja
# ---------------------------------------------------------------------------
def get_children(pid: int, table: str) -> pd.DataFrame:
    if table not in CHILD_COLUMNS:
        raise ValueError(table)
    df = _t(table)
    df = df[df["project_id"] == int(pid)]
    df = df.sort_values(["sort", "id"]) if table == "tasks" else df.sort_values("id")
    return df[["id", *CHILD_COLUMNS[table]]].reset_index(drop=True)


def replace_children(pid: int, table: str, records: list[dict], note: tuple[str, str] | None = None) -> None:
    """Ganti semua baris turunan satu proyek. note = (jenis, pesan) untuk log aktivitas."""
    if table not in CHILD_COLUMNS:
        raise ValueError(table)
    df = _t(table)
    old_ids = df[df["project_id"] == int(pid)]["id"].astype(int).tolist()
    backend().delete_many({table: old_ids})
    backend().insert(table, [{**r, "project_id": int(pid)} for r in records])
    backend().update_many("projects", {int(pid): {"updated_at": now_str()}})
    if note:
        backend().insert("activity", [dict(project_id=int(pid), ts=now_str(), kind=note[0], message=note[1])])
    _written()


def all_children(table: str) -> pd.DataFrame:
    if table not in CHILD_COLUMNS:
        raise ValueError(table)
    tb = _tables()
    p = tb["projects"][["id", "name", "status", "archived", "group_id"]].rename(
        columns={"id": "project_id", "name": "project_name", "status": "project_status"})
    g = tb["groups"][["id", "name", "color"]].rename(columns={"id": "group_id", "name": "group_name", "color": "group_color"})
    g["group_id"] = g["group_id"].astype(float)
    out = tb[table].merge(p, on="project_id", how="inner").merge(g, on="group_id", how="left")
    return out[out["archived"] == 0].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Log aktivitas
# ---------------------------------------------------------------------------
def add_activity(pid: int | None, kind: str, message: str) -> None:
    backend().insert("activity", [dict(project_id=pid, ts=now_str(), kind=kind, message=message)])
    _written()


def project_activity(pid: int, limit: int = 100) -> pd.DataFrame:
    a = _t("activity")
    a = a[a["project_id"] == int(pid)].sort_values(["ts", "id"], ascending=False)
    return a[["id", "ts", "kind", "message"]].head(limit).reset_index(drop=True)


def recent_activity(limit: int = 12) -> pd.DataFrame:
    tb = _tables()
    a = tb["activity"].dropna(subset=["project_id"]).copy()
    a["project_id"] = a["project_id"].astype(int)
    p = tb["projects"][["id", "name", "archived", "group_id"]].rename(columns={"id": "project_id", "name": "project_name"})
    g = tb["groups"][["id", "color"]].rename(columns={"id": "group_id", "color": "group_color"})
    g["group_id"] = g["group_id"].astype(float)
    out = a.merge(p, on="project_id", how="inner").merge(g, on="group_id", how="left")
    out = out[out["archived"] == 0].sort_values(["ts", "id"], ascending=False).head(limit)
    return out[["ts", "kind", "message", "project_id", "project_name", "group_color"]].reset_index(drop=True)


def delete_activity(aid: int) -> None:
    backend().delete_many({"activity": [int(aid)]})
    _written()


# ---------------------------------------------------------------------------
# Ekspor, impor, reset, migrasi
# ---------------------------------------------------------------------------
def export_json() -> str:
    tb = _tables()
    payload = {"app": "project-tracker", "version": 2, "exported_at": now_str()}
    for t in TABLE_ORDER:
        payload[t] = _records(tb[t])
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _replace_everything(data: dict[str, list[dict]]) -> dict:
    counts = {}
    for t in TABLE_ORDER:
        rows = data.get(t) or []
        if t == "meta":
            rows = [r for r in rows if r.get("key")]
            for i, r in enumerate(rows, 1):
                r.setdefault("id", i)
        data[t] = rows
        counts[t] = len(rows)
    backend().replace_many({t: data.get(t) or [] for t in TABLE_ORDER})
    _written()
    return counts


def import_json(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict) or "projects" not in data or "groups" not in data:
        raise ValueError("Format file tidak dikenali. Gunakan file hasil ekspor aplikasi ini.")
    data.setdefault("meta", [])
    if not any(r.get("key") == "initialized" for r in data["meta"]):
        data["meta"].append({"key": "initialized", "value": now_str()})
    return _replace_everything(data)


def copy_from(other_store) -> dict:
    """Salin seluruh isi backend lain (misalnya SQLite lama) ke backend aktif."""
    src = other_store.read_all()
    return _replace_everything({t: _records(src[t]) for t in TABLE_ORDER})


def wipe_all(with_sample: bool = False) -> None:
    if with_sample:
        seed_sample()  # seed_sample sudah mengganti seluruh isi tiap tab
        return
    empty = {t: [] for t in TABLE_ORDER}
    empty["meta"] = [{"id": 1, "key": "initialized", "value": now_str()}]
    backend().replace_many(empty)
    _written()


# ---------------------------------------------------------------------------
# Data contoh: disusun di memori lalu ditulis per tab (hemat panggilan API)
# ---------------------------------------------------------------------------
def seed_sample() -> None:
    t = today()

    def d(offset: int | None) -> str | None:
        return None if offset is None else (t + timedelta(days=offset)).isoformat()

    ts = now_str()
    groups = [
        dict(id=1, name="PT Bhineka Rahsa Nusantara", kind="Perusahaan", color="#0F766E", description="Data & Insight Analyst"),
        dict(id=2, name="PT Indonesia Broadband Communication", kind="Perusahaan", color="#2563EB", description="Retention Program Supervisor"),
        dict(id=3, name="Proyek Pribadi", kind="Pribadi", color="#EA580C", description="Portofolio, produk, dan ide usaha"),
        dict(id=4, name="Studi & Karier", kind="Studi", color="#7C3AED", description="Studi lanjut dan pengembangan diri"),
    ]
    for i, g in enumerate(groups, 1):
        g.update(sort=i, created_at=ts)

    samples = [
        dict(group_id=1, name="Migrasi dashboard ke VPS Tencent", status="Berjalan", priority="Tinggi",
             progress_mode="auto", start_date=d(-20), due_date=d(10), role="Owner teknis",
             stakeholder="Manajemen Rahsa", tags="infra, dashboard",
             description="Memindahkan semua dashboard dan app internal ke satu VPS agar biaya lebih efisien dan deploy lebih cepat.",
             next_action="Migrasi dashboard penjualan lalu uji akses tim",
             tasks=[("Siapkan VPS dan domain", 1, -15), ("Dockerize semua app", 1, -6),
                    ("Migrasi dashboard penjualan", 0, 3), ("Atur backup harian", 0, 6), ("Monitoring dan uji beban", 0, 9)],
             reqs=[("Akses root VPS Tencent", "Akses", "Terpenuhi", ""),
                   ("Domain dan sertifikat SSL", "Akses", "Diproses", "Menunggu DNS"),
                   ("Kredensial database produksi", "Data", "Terpenuhi", "")],
             blockers=[("RAM VPS belum cukup untuk semua container", "Sedang", "Terbuka", -4)],
             files=[("Runbook migrasi", "https://docs.google.com", "Dokumen", "Langkah per app"),
                    ("Repo dashboard", "https://github.com", "Repository", "")]),
        dict(group_id=1, name="Brand Nummu: web belanja ke WhatsApp", status="To Do", priority="Sedang", progress=15,
             start_date=d(-5), due_date=d(30), role="PIC data dan web", tags="web, whatsapp",
             description="Website katalog yang mengarahkan pesanan ke WhatsApp.",
             next_action="Finalisasi daftar produk dan foto",
             reqs=[("Foto produk resolusi tinggi", "Data", "Belum ada", ""), ("Nomor WhatsApp bisnis", "Akses", "Terpenuhi", "")],
             files=[("Katalog produk", "https://docs.google.com/spreadsheets", "Spreadsheet", "")]),
        dict(group_id=1, name="Bot CS WhatsApp", status="Ide", priority="Sedang", due_date=d(60), tags="otomasi",
             description="Bot untuk menjawab pertanyaan pelanggan yang berulang.",
             next_action="Kumpulkan 30 pertanyaan pelanggan teratas"),
        dict(group_id=2, name="OBC Upgrade & Winback", status="Berjalan", priority="Kritis", progress=45,
             start_date=d(-40), due_date=d(70), role="Supervisor", stakeholder="Manager retention",
             tags="retention, campaign", description="Program outbound call upgrade dan winback bulanan per cabang.",
             next_action="Rekap hasil minggu ini per agen",
             reqs=[("Data leads winback per cabang", "Data", "Diproses", "Karawang belum lengkap"),
                   ("Skrip call terbaru", "Informasi", "Terpenuhi", "")],
             blockers=[("Data leads winback cabang Karawang belum lengkap", "Tinggi", "Terbuka", -6)],
             files=[("Tracker target agen", "https://docs.google.com/spreadsheets", "Spreadsheet", "Update harian"),
                    ("Dashboard performa OBC", "https://lookerstudio.google.com", "Dashboard", "")]),
        dict(group_id=2, name="Program referral MGM (NC & RC)", status="Review", priority="Tinggi", progress=80,
             start_date=d(-25), due_date=d(3), role="Penyusun usulan", tags="referral, akuisisi",
             description="Usulan program member get member untuk new connect dan reconnect.",
             next_action="Revisi skema reward sesuai masukan",
             reqs=[("Persetujuan anggaran reward", "Persetujuan", "Diproses", "")],
             files=[("Deck usulan MGM", "https://docs.google.com/presentation", "Presentasi", "")]),
        dict(group_id=2, name="Riset kerja sama Indomaret", status="Berjalan", priority="Sedang", progress=60,
             start_date=d(-30), due_date=d(-2), tags="partnership, riset",
             description="Eksplorasi opsi voucher, poin, dan bundling bersama mitra ritel.",
             next_action="Kirim ringkasan opsi ke atasan",
             blockers=[("Belum ada kontak resmi di pihak mitra", "Sedang", "Terbuka", -10)]),
        dict(group_id=3, name="Market Basket Analysis App", status="Berjalan", priority="Sedang", progress_mode="auto",
             start_date=d(-35), due_date=d(14), tags="portofolio, streamlit",
             description="App rekomendasi bundling produk untuk portofolio.", next_action="Tulis README dan deploy",
             tasks=[("Bersihkan dataset", 1, -28), ("Model apriori dan FP-Growth", 1, -18),
                    ("Visual jaringan produk", 1, -8), ("README dan studi kasus", 0, 7), ("Deploy", 0, 12)],
             files=[("Repo MBA", "https://github.com", "Repository", "")]),
        dict(group_id=3, name="NeroCar / CarDikha", status="Ide", priority="Rendah", progress=5, tags="startup, otomotif",
             description="Platform website dan leads untuk dealer dan sales mobil.",
             next_action="Validasi ide dengan 5 sales mobil"),
        dict(group_id=3, name="Aplikasi stok baja ringan", status="Selesai", priority="Sedang", progress=100,
             start_date=d(-60), due_date=d(-15), tags="streamlit, google sheet",
             description="Laporan stok berbasis Streamlit dan Google Sheet."),
        dict(group_id=4, name="Persiapan Chevening & S2 Edinburgh", status="Berjalan", priority="Tinggi",
             progress_mode="auto", start_date=d(-14), due_date=d(20), tags="beasiswa, S2",
             description="Menyiapkan esai, referensi, dan dokumen pendaftaran.",
             next_action="Selesaikan draf esai leadership",
             tasks=[("Draf esai leadership", 0, 4), ("Draf esai networking", 0, 8), ("Draf esai career plan", 0, 12),
                    ("Minta 2 surat referensi", 1, -3), ("Siapkan transkrip", 1, -7)],
             reqs=[("Surat referensi", "Persetujuan", "Diproses", ""), ("Skor IELTS", "Lainnya", "Belum ada", "")],
             blockers=[("Jadwal tes IELTS belum tersedia", "Tinggi", "Terbuka", -2)],
             files=[("Folder dokumen beasiswa", "https://drive.google.com", "Folder", "")]),
    ]

    out = {k: [] for k in TABLE_ORDER}
    out["groups"] = groups
    seq = {k: 1 for k in TABLE_ORDER}

    def add(table: str, rec: dict) -> int:
        rec["id"] = seq[table]
        seq[table] += 1
        out[table].append(rec)
        return rec["id"]

    done_ts = (datetime.combine(t, datetime.min.time()) - timedelta(days=16)).strftime("%Y-%m-%d %H:%M:%S")
    for s in samples:
        tasks, reqs = s.pop("tasks", []), s.pop("reqs", [])
        blockers, files = s.pop("blockers", []), s.pop("files", [])
        rec = _project_record(s)
        if rec["status"] == "Selesai":
            rec["completed_at"] = done_ts
        pid = add("projects", rec)
        add("activity", dict(project_id=pid, ts=ts, kind="dibuat", message=f"Proyek dibuat dengan status {rec['status']}"))
        for i, (title, done, off) in enumerate(tasks):
            add("tasks", dict(project_id=pid, title=title, done=done, due_date=d(off), sort=i))
        for item, cat, stt, notes in reqs:
            add("requirements", dict(project_id=pid, item=item, category=cat, status=stt, notes=notes))
        for desc, sev, stt, off in blockers:
            add("blockers", dict(project_id=pid, description=desc, severity=sev, status=stt, raised_at=d(off),
                                 resolved_at=None, resolution=""))
        for name, url, ftype, notes in files:
            add("files", dict(project_id=pid, name=name, url=url, ftype=ftype, notes=notes, added_at=d(-1)))

    out["meta"] = [{"id": 1, "key": "initialized", "value": ts}]
    backend().replace_many(out)
    _written()
