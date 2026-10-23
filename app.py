"""Project Tracker pribadi.

Jalankan:  streamlit run app.py
"""
from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import db, logic, state, store, ui  # noqa: E402
from core.timeutil import fmt_day_long, today  # noqa: E402
from views import board, dashboard, detail, groups, projects, settings  # noqa: E402

st.set_page_config(
    page_title="Project Tracker",
    page_icon=":material/view_kanban:",
    layout="wide",
    initial_sidebar_state="expanded",
)


ui.inject_css()

try:
    db.backend()
    db.init_db(seed_if_new=os.environ.get("TRACKER_SEED", "1") == "1")
except store.StoreConfigError as exc:
    ui.page_header("Google Sheet belum terhubung", "Lengkapi konfigurasi lalu muat ulang halaman.")
    st.error(str(exc), icon=":material/error:")
    st.markdown(
        "Langkah singkat (detail di README):\n"
        "1. Aktifkan **Google Sheets API** di Google Cloud Console.\n"
        "2. Buat **service account**, unduh kunci JSON.\n"
        "3. Buat Google Sheet kosong, **bagikan ke email service account sebagai Editor**.\n"
        "4. Isi `.streamlit/secrets.toml` (contoh ada di `secrets.toml.example`).\n\n"
        "Ingin memakai SQLite lokal dulu? Hapus baris `spreadsheet` di secrets atau set `backend = \"sqlite\"`."
    )
    st.stop()
except Exception as exc:  # noqa: BLE001  (kuota API, jaringan, dll)
    ui.page_header("Gagal memuat data", "Coba muat ulang halaman beberapa saat lagi.")
    st.exception(exc)
    st.stop()

state.PAGES.update({
    "dashboard": st.Page(dashboard.render, title="Ringkasan", icon=":material/space_dashboard:", url_path="ringkasan", default=True),
    "board": st.Page(board.render, title="Papan Kanban", icon=":material/view_kanban:", url_path="papan"),
    "list": st.Page(projects.render, title="Daftar Proyek", icon=":material/table_rows:", url_path="daftar"),
    "detail": st.Page(detail.render, title="Detail Proyek", icon=":material/folder_open:", url_path="detail"),
    "groups": st.Page(groups.render, title="Grup & Sumber", icon=":material/workspaces:", url_path="grup"),
    "settings": st.Page(settings.render, title="Data & Pengaturan", icon=":material/tune:", url_path="pengaturan"),
})

nav = st.navigation({
    "Ruang kerja": [state.PAGES[k] for k in ("dashboard", "board", "list", "detail")],
    "Kelola": [state.PAGES[k] for k in ("groups", "settings")],
})

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")
if os.path.exists(LOGO):
    st.logo(LOGO, size="large")

with st.sidebar:
    if st.button("Proyek baru", type="primary", icon=":material/add:", width="stretch", key="sb_new"):
        state.new_project_dialog()
    _info = db.backend_info()
    s1, s2 = st.columns(2, gap="small")
    if s1.button("Sinkron", icon=":material/sync:", width="stretch", key="sb_sync",
                 help="Muat ulang data terbaru dari sumber"):
        db.refresh()
        st.rerun()
    if _info.get("url"):
        s2.link_button("Sheet", _info["url"], icon=":material/table_view:", width="stretch",
                       help="Buka Google Sheet database")
    df_side = logic.load_projects()
    s = logic.summary(df_side)
    ui.html(
        '<div style="margin-top:14px" class="pt-label">Sekilas</div>'
        f'<div class="pt-side-stat"><span>Proyek aktif</span><b>{s["active"]}</b></div>'
        f'<div class="pt-side-stat"><span>Rata-rata progres</span><b>{s["avg_progress"]}%</b></div>'
        f'<div class="pt-side-stat"><span>Perlu perhatian</span><b style="color:{ui.HEALTH_COLORS["Berisiko"] if s["late"] + s["risk"] else ui.INK}">{s["late"] + s["risk"]}</b></div>'
        f'<div class="pt-side-stat"><span>Hambatan terbuka</span><b>{s["blockers"]}</b></div>'
        f'<div style="margin-top:14px;font-size:12px;color:{ui.MUTED}">{fmt_day_long(today())}'
        f'<br>Data: {ui.esc(_info["backend"])}</div>'
    )

state.show_flash()
nav.run()
