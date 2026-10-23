"""Halaman Daftar Proyek: tabel per grup / sumber proyek."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import db, logic, state, ui
from core.timeutil import days_label

COLUMN_CONFIG = {
    "id": None,
    "Proyek": st.column_config.TextColumn("Proyek", width=240, pinned=True),
    "Grup": st.column_config.TextColumn("Grup", width=190),
    "Status": st.column_config.TextColumn("Status", width=85),
    "Prioritas": st.column_config.TextColumn("Prioritas", width=80),
    "Progres": st.column_config.ProgressColumn("Progres", min_value=0, max_value=100, format="%d%%", width=110),
    "Kesehatan": st.column_config.TextColumn("Kesehatan", width=90),
    "Tenggat": st.column_config.DateColumn("Tenggat", format="DD/MM/YYYY", width=95),
    "Sisa": st.column_config.TextColumn("Sisa waktu", width=105),
    "Tugas": st.column_config.TextColumn("Tugas", width=60),
    "Hambatan": st.column_config.NumberColumn("Hambatan", width=80),
    "Kebutuhan": st.column_config.TextColumn("Kebutuhan", width=85, help="Terpenuhi / total"),
    "Langkah berikutnya": st.column_config.TextColumn("Langkah berikutnya", width=260),
    "Link": st.column_config.LinkColumn("Link", display_text="Buka", width=60),
}

HEALTH_MARK = {"Aman": "Aman", "Berisiko": "Berisiko", "Terlambat": "Terlambat", "Selesai": "Selesai"}


def _table(df: pd.DataFrame, with_group: bool) -> pd.DataFrame:
    out = pd.DataFrame({
        "id": df["id"],
        "Proyek": df["name"],
        "Grup": df["group_name"],
        "Status": df["status"],
        "Prioritas": df["priority"],
        "Progres": df["progress_eff"].astype(int),
        "Kesehatan": df["health"].map(HEALTH_MARK),
        "Tenggat": pd.to_datetime(df["due_date"], errors="coerce"),
        "Sisa": [days_label(d) if s != "Selesai" else "-" for d, s in zip(df["days_left"], df["status"])],
        "Tugas": [f"{int(d)}/{int(t)}" if t else "-" for d, t in zip(df["tasks_done"], df["tasks_total"])],
        "Hambatan": df["blockers_open"].astype(int),
        "Kebutuhan": [f"{int(d)}/{int(t)}" if t else "-" for d, t in zip(df["req_done"], df["req_total"])],
        "Langkah berikutnya": df["next_action"].fillna(""),
        "Link": df["main_link"].replace("", None),
    })
    if not with_group:
        out = out.drop(columns=["Grup"])
    return out


def _grid(df: pd.DataFrame, key: str, with_group: bool) -> None:
    table = _table(df, with_group)
    event = st.dataframe(
        table, hide_index=True, width="stretch", column_config=COLUMN_CONFIG,
        on_select="rerun", selection_mode="single-row", key=key,
        height=min(38 + 35 * len(table), 520),
    )
    rows = event.selection.rows if event and event.selection else []
    if rows:
        pid = int(table.iloc[rows[0]]["id"])
        name = table.iloc[rows[0]]["Proyek"]
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.caption(f"Dipilih: {name}")
        if c2.button("Buka detail", key=f"{key}_open", icon=":material/arrow_forward:", type="primary", width="stretch"):
            state.go_detail(pid)


def render() -> None:
    df = logic.load_projects(include_archived=st.session_state.get("list_archived", False))
    ui.page_header("Daftar proyek", "Semua proyek dikelompokkan berdasarkan grup atau sumbernya. Pilih satu baris untuk membuka detail.")

    c1, c2, c3, c4 = st.columns([1.4, 2, 2, 1.2], gap="small", vertical_alignment="bottom")
    mode = c1.segmented_control("Tampilan", ["Per grup", "Satu tabel"], default="Per grup", key="list_mode",
                                label_visibility="collapsed") or "Per grup"
    stat = c2.multiselect("Status", db.STATUSES, key="list_status", placeholder="Semua status", label_visibility="collapsed")
    health = c3.multiselect("Kesehatan", logic.HEALTH_ORDER, key="list_health", placeholder="Semua kesehatan",
                            label_visibility="collapsed")
    c4.toggle("Arsip", key="list_archived", help="Tampilkan juga proyek yang diarsipkan")

    view = df
    if stat:
        view = view[view["status"].isin(stat)]
    if health:
        view = view[view["health"].isin(health)]

    if view.empty:
        st.info("Tidak ada proyek yang cocok dengan filter.", icon=":material/info:")
        return

    if mode == "Satu tabel":
        _grid(view, "grid_all", with_group=True)
    else:
        groups = logic.by_group(view)
        for _, g in groups.iterrows():
            part = view[view["group_name"] == g["group_name"]]
            ui.html(
                f'<div class="pt-section" style="margin-top:22px">'
                f'<h3 style="display:flex;align-items:center;gap:10px"><i class="pt-dot" style="background:{g["group_color"]};width:12px;height:12px;border-radius:3px"></i>{ui.esc(g["group_name"])}</h3>'
                f'<span>{g["open"]} terbuka · {g["done"]} selesai · rata-rata progres {g["avg_progress"]}%</span></div>'
            )
            _grid(part, f"grid_{abs(hash(g['group_name']))}", with_group=False)

    st.download_button(
        "Unduh CSV", data=_table(view, True).drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
        file_name="daftar_proyek.csv", mime="text/csv", icon=":material/download:",
    )
