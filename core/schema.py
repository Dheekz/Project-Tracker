"""Definisi tabel (= tab di Google Sheet), tipe kolom, dan kosakata pilihan."""
from __future__ import annotations

STATUSES = ["Ide", "To Do", "Berjalan", "Review", "Tertunda", "Selesai"]
ACTIVE_STATUSES = ["To Do", "Berjalan", "Review"]
PRIORITIES = ["Rendah", "Sedang", "Tinggi", "Kritis"]
PROGRESS_MODES = ["manual", "auto"]
GROUP_KINDS = ["Perusahaan", "Klien", "Pribadi", "Studi", "Komunitas", "Lainnya"]
REQ_CATEGORIES = ["Data", "Akses", "Tools", "Anggaran", "SDM", "Persetujuan", "Informasi", "Lainnya"]
REQ_STATUSES = ["Belum ada", "Diproses", "Terpenuhi"]
BLOCKER_SEVERITIES = ["Rendah", "Sedang", "Tinggi", "Kritis"]
BLOCKER_STATUSES = ["Terbuka", "Selesai"]
FILE_TYPES = ["Spreadsheet", "Dokumen", "Presentasi", "Dashboard", "Repository", "Folder", "Desain", "Lainnya"]

# Tipe kolom:
#   int   = bilangan bulat wajib (kosong dianggap 0)
#   intn  = bilangan bulat boleh kosong (misalnya group_id)
#   text  = teks bebas
#   date  = tanggal, disimpan sebagai YYYY-MM-DD
#   ts    = waktu, disimpan sebagai YYYY-MM-DD HH:MM:SS
TABLES: dict[str, dict[str, str]] = {
    "groups": {
        "id": "int", "name": "text", "kind": "text", "color": "text", "description": "text",
        "sort": "int", "created_at": "ts",
    },
    "projects": {
        "id": "int", "group_id": "intn", "name": "text", "description": "text", "status": "text",
        "priority": "text", "progress": "int", "progress_mode": "text", "start_date": "date",
        "due_date": "date", "main_link": "text", "tags": "text", "role": "text", "stakeholder": "text",
        "next_action": "text", "pinned": "int", "archived": "int", "created_at": "ts",
        "updated_at": "ts", "completed_at": "ts",
    },
    "tasks": {
        "id": "int", "project_id": "int", "title": "text", "done": "int", "due_date": "date", "sort": "int",
    },
    "requirements": {
        "id": "int", "project_id": "int", "item": "text", "category": "text", "status": "text", "notes": "text",
    },
    "blockers": {
        "id": "int", "project_id": "int", "description": "text", "severity": "text", "status": "text",
        "raised_at": "date", "resolved_at": "date", "resolution": "text",
    },
    "files": {
        "id": "int", "project_id": "int", "name": "text", "url": "text", "ftype": "text",
        "notes": "text", "added_at": "date",
    },
    "activity": {
        "id": "int", "project_id": "intn", "ts": "ts", "kind": "text", "message": "text",
    },
    "meta": {"id": "int", "key": "text", "value": "text"},
}

TABLE_ORDER = ["groups", "projects", "tasks", "requirements", "blockers", "files", "activity", "meta"]

# Kolom teks yang nilainya wajib dari daftar tertentu (dipakai untuk validasi
# dropdown di Google Sheet dan untuk membersihkan input manual).
CHOICES: dict[tuple[str, str], tuple[list[str], str]] = {
    ("groups", "kind"): (GROUP_KINDS, "Lainnya"),
    ("projects", "status"): (STATUSES, "To Do"),
    ("projects", "priority"): (PRIORITIES, "Sedang"),
    ("projects", "progress_mode"): (PROGRESS_MODES, "manual"),
    ("requirements", "category"): (REQ_CATEGORIES, "Lainnya"),
    ("requirements", "status"): (REQ_STATUSES, "Belum ada"),
    ("blockers", "severity"): (BLOCKER_SEVERITIES, "Sedang"),
    ("blockers", "status"): (BLOCKER_STATUSES, "Terbuka"),
    ("files", "ftype"): (FILE_TYPES, "Lainnya"),
}

# Kolom yang wajib terisi; baris tanpa nilai ini diabaikan saat dibaca.
REQUIRED = {
    "groups": "name", "projects": "name", "tasks": "title", "requirements": "item",
    "blockers": "description", "files": "name", "activity": "message", "meta": "key",
}

DEFAULTS = {"color": "#0F766E"}
