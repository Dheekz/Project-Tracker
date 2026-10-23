"""Halaman Data & Pengaturan: sumber data, sinkron, backup, migrasi, reset."""
from __future__ import annotations

import os

import streamlit as st

from core import db, logic, state, store, ui
from core.timeutil import now


def render() -> None:
    ui.page_header("Data & pengaturan", "Sumber data, sinkronisasi dengan Google Sheet, backup, dan reset.")
    info = db.backend_info()
    is_sheet = db.backend().kind == "gsheets"

    df = logic.load_projects(include_archived=True)
    c1, c2, c3 = st.columns(3, gap="small")
    c1.markdown(ui.kpi("Sumber data", info["backend"], ui.esc(info.get("title") or ""), ui.PRIMARY, "box"),
                unsafe_allow_html=True)
    c2.markdown(ui.kpi("Total proyek", len(df), "termasuk arsip", "#2563EB", "layers"), unsafe_allow_html=True)
    c3.markdown(ui.kpi("Grup", len(db.list_groups()), "sumber proyek", ui.ACCENT, "target"), unsafe_allow_html=True)

    ui.section("Sinkronisasi", f"cache baca {store.config()['cache_ttl']} detik")
    b1, b2 = st.columns([1, 1])
    if b1.button("Muat ulang data sekarang", icon=":material/sync:", width="stretch",
                 help="Ambil data terbaru, misalnya setelah Anda mengedit langsung di Google Sheet"):
        db.refresh()
        state.flash("Data dimuat ulang dari sumber")
        st.rerun()
    if is_sheet and info.get("url"):
        b2.link_button("Buka Google Sheet", info["url"], icon=":material/table_view:", width="stretch")
    if not is_sheet:
        st.info("Aplikasi sedang memakai SQLite lokal karena Google Sheet belum dikonfigurasi. "
                "Ikuti langkah di README bagian Setup Google Sheet, lalu restart aplikasi.", icon=":material/info:")

    if is_sheet and os.path.exists(store.DEFAULT_SQLITE):
        ui.section("Migrasi dari SQLite lama", "satu kali saja")
        st.caption(f"Ditemukan database lokal versi sebelumnya: {store.DEFAULT_SQLITE}. "
                   "Salin isinya ke Google Sheet. Isi Sheet saat ini akan diganti.")
        if st.button("Salin data SQLite ke Google Sheet", icon=":material/move_up:"):
            with st.spinner("Menyalin data ke Google Sheet..."):
                counts = db.copy_from(store.SqliteStore(store.DEFAULT_SQLITE))
            state.flash(f"Migrasi selesai: {counts.get('projects', 0)} proyek, {counts.get('groups', 0)} grup")
            st.rerun()

    ui.section("Backup", "simpan salinan rutin, misalnya tiap Jumat")
    st.download_button(
        "Unduh backup (JSON)", data=db.export_json().encode("utf-8"),
        file_name=f"backup_tracker_{now():%Y%m%d_%H%M}.json", mime="application/json",
        icon=":material/download:", type="primary",
    )

    ui.section("Pulihkan dari backup", "mengganti seluruh data saat ini")
    up = st.file_uploader("File backup JSON", type=["json"], label_visibility="collapsed")
    if up is not None:
        st.warning("Semua data saat ini akan diganti dengan isi file backup.", icon=":material/warning:")
        if st.button("Pulihkan sekarang", icon=":material/restore:"):
            try:
                with st.spinner("Memulihkan data..."):
                    counts = db.import_json(up.getvalue().decode("utf-8"))
                state.flash(f"Data dipulihkan: {counts.get('projects', 0)} proyek, {counts.get('groups', 0)} grup")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Gagal memulihkan: {exc}")

    ui.section("Reset data", "")
    with st.container(border=True, key="panel_reset"):
        st.markdown("**Kosongkan semua data** untuk mulai dari nol dengan proyek Anda sendiri, "
                    "atau **muat ulang data contoh** untuk mencoba fitur.")
        confirm = st.text_input("Ketik RESET untuk mengaktifkan tombol", key="reset_confirm")
        r1, r2 = st.columns(2)
        if r1.button("Kosongkan semua data", disabled=confirm.strip() != "RESET", icon=":material/delete_sweep:", width="stretch"):
            with st.spinner("Mengosongkan data..."):
                db.wipe_all(with_sample=False)
            state.flash("Semua data dikosongkan", "warning")
            st.rerun()
        if r2.button("Muat ulang data contoh", disabled=confirm.strip() != "RESET", icon=":material/refresh:", width="stretch"):
            with st.spinner("Memuat data contoh..."):
                db.wipe_all(with_sample=True)
            state.flash("Data contoh dimuat ulang")
            st.rerun()

    if is_sheet:
        ui.section("Aturan edit langsung di Google Sheet", "")
        st.markdown(
            """
- **Jangan ubah nama tab dan baris judul kolom.** Urutan kolom boleh diubah, kolom tambahan Anda sendiri boleh ditaruh di kanan.
- **Kolom `id` boleh dikosongkan** saat menambah baris baru. Aplikasi mengisinya otomatis saat data dimuat.
- **`group_id` di tab projects** dan **`project_id` di tab tugas, kebutuhan, hambatan, file** harus diisi dengan `id` dari tab induknya.
- **Tanggal** tulis `2026-10-31` atau ketik sebagai tanggal biasa. Keduanya terbaca.
- **Kolom pilihan** (status, prioritas, kategori, dll) sudah diberi dropdown. Nilai di luar daftar diganti ke nilai bawaan.
- **`done`, `pinned`, `archived`** isi `1` untuk ya, `0` atau kosong untuk tidak.
- Perubahan di Sheet muncul di aplikasi setelah cache habis, atau langsung lewat tombol **Muat ulang data sekarang**.
"""
        )
