"""State bersama: registri halaman, navigasi ke detail, dialog proyek baru."""
from __future__ import annotations

import streamlit as st

from core import db
from core.timeutil import today

PAGES: dict[str, st.Page] = {}


def go_detail(pid: int) -> None:
    st.session_state["selected_project"] = int(pid)
    st.switch_page(PAGES["detail"], query_params={"id": str(int(pid))})


def flash(message: str, kind: str = "success") -> None:
    """Simpan pesan untuk ditampilkan setelah rerun."""
    st.session_state["_flash"] = (message, kind)


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        msg, kind = item
        icons = {"success": ":material/check_circle:", "info": ":material/info:", "warning": ":material/warning:"}
        st.toast(msg, icon=icons.get(kind, ":material/info:"))


def _group_options() -> tuple[list, dict]:
    groups = db.list_groups()
    ids = [None] + groups["id"].tolist()
    labels = {None: "Tanpa grup"} | dict(zip(groups["id"], groups["name"]))
    return ids, labels


@st.dialog("Proyek baru", width="large", icon=":material/add_circle:")
def new_project_dialog(default_status: str = "To Do", default_group: int | None = None) -> None:
    ids, labels = _group_options()
    if len(ids) == 1:
        st.info("Belum ada grup. Buat grup di halaman Grup & Sumber agar proyek bisa dikelompokkan.", icon=":material/info:")
    with st.form("form_new_project", border=False):
        name = st.text_input("Nama proyek", placeholder="Contoh: Dashboard retensi pelanggan")
        c1, c2 = st.columns(2)
        gidx = ids.index(default_group) if default_group in ids else (1 if len(ids) > 1 else 0)
        group_id = c1.selectbox("Grup / sumber proyek", ids, index=gidx, format_func=lambda x: labels[x])
        status = c2.selectbox("Status", db.STATUSES, index=db.STATUSES.index(default_status))
        c3, c4 = st.columns(2)
        priority = c3.selectbox("Prioritas", db.PRIORITIES, index=1)
        mode = c4.selectbox(
            "Cara hitung progres", ["manual", "auto"],
            format_func=lambda x: "Manual (geser sendiri)" if x == "manual" else "Otomatis dari checklist tugas",
        )
        c5, c6 = st.columns(2)
        start = c5.date_input("Tanggal mulai", value=today(), format="DD/MM/YYYY")
        due = c6.date_input("Tenggat", value=None, format="DD/MM/YYYY")
        link = st.text_input("Link utama proyek", placeholder="https://")
        desc = st.text_area("Deskripsi singkat", height=80)
        nxt = st.text_input("Langkah berikutnya", placeholder="Satu aksi konkret yang harus dikerjakan berikutnya")
        c7, c8 = st.columns(2)
        role = c7.text_input("Peran saya", placeholder="Owner, PIC, kontributor")
        stakeholder = c8.text_input("Pemberi tugas / stakeholder")
        tags = st.text_input("Tag", placeholder="Pisahkan dengan koma, contoh: dashboard, retention")
        submitted = st.form_submit_button("Simpan proyek", type="primary", icon=":material/check:")

    if submitted:
        if not name.strip():
            st.error("Nama proyek wajib diisi.")
            return
        if due and start and due < start:
            st.error("Tenggat tidak boleh lebih awal dari tanggal mulai.")
            return
        pid = db.create_project(dict(
            name=name.strip(), group_id=group_id, status=status, priority=priority, progress_mode=mode,
            progress=0, start_date=start.isoformat() if start else None, due_date=due.isoformat() if due else None,
            main_link=link.strip(), description=desc.strip(), next_action=nxt.strip(), role=role.strip(),
            stakeholder=stakeholder.strip(), tags=tags.strip(),
        ))
        st.session_state["selected_project"] = pid
        flash(f"Proyek \"{name.strip()}\" ditambahkan")
        st.rerun()
