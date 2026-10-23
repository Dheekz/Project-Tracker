"""Halaman Papan Kanban: proyek per status, mirip Trello / Lark."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import db, logic, state, ui


def _filters(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns([2.2, 2, 1.6, 1.2], gap="small", vertical_alignment="bottom")
    q = c1.text_input("Cari", placeholder="Cari nama, tag, atau deskripsi", key="board_q",
                      label_visibility="collapsed")
    groups = sorted(df["group_name"].unique().tolist()) if not df.empty else []
    g = c2.multiselect("Grup", groups, key="board_groups", placeholder="Semua grup", label_visibility="collapsed")
    p = c3.multiselect("Prioritas", db.PRIORITIES, key="board_prio", placeholder="Semua prioritas",
                       label_visibility="collapsed")
    st.session_state.setdefault("board_show_done", False)
    c4.toggle("Kolom Selesai", key="board_show_done")
    out = df
    if q:
        ql = q.lower()
        hay = (out["name"].fillna("") + " " + out["tags"].fillna("") + " " + out["description"].fillna("")).str.lower()
        out = out[hay.str.contains(ql, regex=False)]
    if g:
        out = out[out["group_name"].isin(g)]
    if p:
        out = out[out["priority"].isin(p)]
    return out


def _sort(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_p"] = df["priority"].map(ui.PRIORITY_RANK).fillna(9)
    df["_d"] = pd.to_datetime(df["due_date"], errors="coerce")
    return df.sort_values(["pinned", "_p", "_d"], ascending=[False, True, True], na_position="last")


def render() -> None:
    df = logic.load_projects()
    ui.page_header("Papan kanban", "Pindahkan proyek antar kolom lewat tombol Status. Klik Buka untuk melihat detail lengkap.")
    view = _filters(df)

    statuses = [s for s in db.STATUSES if st.session_state.get("board_show_done", False) or s != "Selesai"]
    cols = st.columns(len(statuses), gap="small")
    for col, status in zip(cols, statuses):
        sub = _sort(view[view["status"] == status])
        color = ui.STATUS_COLORS[status]
        with col:
            ui.html(
                f'<div class="pt-col-head" style="border-top-color:{color}">'
                f'<span style="display:flex;align-items:center;gap:8px"><i class="pt-dot" style="background:{color}"></i>'
                f'<b>{status}</b></span><span class="pt-count">{len(sub)}</span></div>'
            )
            if sub.empty:
                ui.html('<div class="pt-empty">Belum ada proyek</div>')
            for _, row in sub.iterrows():
                _card(row.to_dict())
            if st.button("Tambah", key=f"add_{status}", icon=":material/add:", width="stretch", type="tertiary"):
                state.new_project_dialog(default_status=status)


def _card(row: dict) -> None:
    pid = int(row["id"])
    with st.container(border=True, key=f"card_{pid}"):
        ui.html(ui.project_card(row))
        b1, b2 = st.columns(2, gap="small")
        if b1.button("Buka", key=f"open_{pid}", width="stretch", help="Buka detail proyek"):
            state.go_detail(pid)
        with b2.popover("Status", width="stretch", help="Pindahkan ke status lain"):
            st.markdown(f"**{ui.esc(row['name'])}**")
            st.caption("Pindahkan ke status:")
            for s in db.STATUSES:
                if s == row["status"]:
                    continue
                if st.button(s, key=f"mv_{pid}_{s}", width="stretch"):
                    db.set_status(pid, s)
                    state.flash(f"\"{row['name']}\" dipindah ke {s}")
                    st.rerun()
            if ui.has(row.get("main_link")):
                st.divider()
                st.link_button("Buka link proyek", row["main_link"], icon=":material/link:", width="stretch")
