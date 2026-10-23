"""Halaman Grup & Sumber: kelola asal proyek (perusahaan, klien, pribadi, dll)."""
from __future__ import annotations

import streamlit as st

from core import db, logic, state, ui


def render() -> None:
    ui.page_header(
        "Grup & sumber proyek",
        "Kelompokkan proyek berdasarkan asalnya, misalnya perusahaan tempat bekerja, klien freelance, atau proyek pribadi.",
    )
    groups = db.list_groups()
    stats = logic.by_group(logic.load_projects()).set_index("group_name") if not groups.empty else None

    with st.expander("Tambah grup baru", icon=":material/add:", expanded=groups.empty):
        with st.form("new_group", clear_on_submit=True, border=False):
            c1, c2, c3 = st.columns([3, 2, 1])
            name = c1.text_input("Nama grup", placeholder="Contoh: PT Maju Jaya")
            kind = c2.selectbox("Jenis", db.GROUP_KINDS)
            color = c3.color_picker("Warna", ui.GROUP_PALETTE[len(groups) % len(ui.GROUP_PALETTE)])
            desc = st.text_input("Keterangan", placeholder="Contoh: posisi atau peran saya di sana")
            if st.form_submit_button("Simpan grup", type="primary", icon=":material/check:"):
                if not name.strip():
                    st.error("Nama grup wajib diisi.")
                elif name.strip().lower() in groups["name"].str.lower().tolist():
                    st.error("Nama grup sudah ada.")
                else:
                    db.create_group(name, kind, color, desc)
                    state.flash(f"Grup \"{name.strip()}\" ditambahkan")
                    st.rerun()

    if groups.empty:
        st.info("Belum ada grup.", icon=":material/info:")
        return

    ui.section("Semua grup", f"{len(groups)} grup")
    per_row = 3
    records = groups.to_dict("records")
    for start in range(0, len(records), per_row):
        cols = st.columns(per_row, gap="small")
        for col, g in zip(cols, records[start:start + per_row]):
            with col:
                _group_card(g, stats, groups)


def _group_card(g: dict, stats, groups) -> None:
    s = stats.loc[g["name"]] if stats is not None and g["name"] in stats.index else None
    open_n = int(s["open"]) if s is not None else 0
    done_n = int(s["done"]) if s is not None else 0
    avg = int(s["avg_progress"]) if s is not None and open_n else 0
    blk = int(s["blockers"]) if s is not None else 0
    ui.html(
        f'<div class="pt-gcard" style="--gc:{g["color"]}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">'
        f'<div><div class="pt-gcard-name">{ui.esc(g["name"])}</div>'
        f'<div class="pt-gcard-kind">{ui.esc(g["description"]) or "Tanpa keterangan"}</div></div>'
        f'{ui.badge(g["kind"], g["color"])}</div>'
        f'<div class="pt-gstats"><div><b>{open_n}</b>terbuka</div><div><b>{done_n}</b>selesai</div><div><b>{blk}</b>hambatan</div></div>'
        f'<div style="margin-top:12px">{ui.progress_bar(avg, g["color"])}</div></div>'
    )
    with st.popover("Ubah / hapus", icon=":material/edit:", width="stretch"):
        gid = int(g["id"])
        with st.form(f"edit_group_{gid}", border=False):
            name = st.text_input("Nama", g["name"])
            kind = st.selectbox("Jenis", db.GROUP_KINDS,
                                index=db.GROUP_KINDS.index(g["kind"]) if g["kind"] in db.GROUP_KINDS else 0)
            color = st.color_picker("Warna", g["color"])
            desc = st.text_input("Keterangan", g["description"] or "")
            if st.form_submit_button("Simpan", type="primary"):
                others = groups[groups["id"] != gid]["name"].str.lower().tolist()
                if not name.strip():
                    st.error("Nama wajib diisi.")
                elif name.strip().lower() in others:
                    st.error("Nama grup sudah dipakai.")
                else:
                    db.update_group(gid, name, kind, color, desc)
                    state.flash("Grup diperbarui")
                    st.rerun()
        st.divider()
        others = groups[groups["id"] != gid]
        options = [None] + others["id"].tolist()
        labels = {None: "Tanpa grup"} | dict(zip(others["id"], others["name"]))
        move_to = st.selectbox("Pindahkan proyeknya ke", options, format_func=lambda x: labels[x], key=f"mv_grp_{gid}")
        if st.button("Hapus grup", key=f"del_grp_{gid}", icon=":material/delete:"):
            db.delete_group(gid, move_to)
            state.flash("Grup dihapus, proyek sudah dipindahkan", "warning")
            st.rerun()
