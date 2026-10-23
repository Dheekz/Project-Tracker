"""Halaman Detail Proyek: info lengkap, tugas, kebutuhan, hambatan, file kerja, catatan."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import db, logic, state, ui
from core.timeutil import days_label, fmt_date, fmt_ts, parse_date, relative_ts, today

FILE_ICON = {
    "Spreadsheet": ("#15803D", "box"), "Dokumen": ("#2563EB", "box"), "Presentasi": ("#EA580C", "box"),
    "Dashboard": ("#7C3AED", "pulse"), "Repository": ("#0F172A", "layers"), "Folder": ("#B45309", "box"),
    "Desain": ("#DB2777", "target"), "Lainnya": ("#64748B", "clip"),
}


# ---------------------------------------------------------------------------
# Pemilihan proyek
# ---------------------------------------------------------------------------
def _resolve_selected(df: pd.DataFrame) -> int | None:
    qp = st.query_params.get("id")
    if qp and str(qp).isdigit() and int(qp) in set(df["id"].tolist()):
        st.session_state["selected_project"] = int(qp)
    sel = st.session_state.get("selected_project")
    if sel in set(df["id"].tolist()):
        return int(sel)
    return int(df.iloc[0]["id"]) if not df.empty else None


def render() -> None:
    df = logic.load_projects(include_archived=True)
    if df.empty:
        ui.page_header("Detail proyek", "Belum ada proyek.")
        if st.button("Buat proyek pertama", type="primary", icon=":material/add:"):
            state.new_project_dialog()
        return

    pid = _resolve_selected(df)
    ordered = df.sort_values(["archived", "group_name", "name"])
    ids = ordered["id"].tolist()
    labels = dict(zip(ordered["id"], ordered["group_name"] + "  /  " + ordered["name"]
                      + ordered["archived"].map({1: "  (arsip)", 0: ""})))

    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    chosen = c1.selectbox("Pilih proyek", ids, index=ids.index(pid), format_func=lambda x: labels[x], key=f"detail_pick_{pid}")
    if chosen != pid:
        st.session_state["selected_project"] = int(chosen)
        st.query_params["id"] = str(int(chosen))
        st.rerun()
    if c2.button("Proyek baru", icon=":material/add:", width="stretch"):
        state.new_project_dialog()

    st.query_params["id"] = str(pid)
    row = df[df["id"] == pid].iloc[0].to_dict()
    _header(row)
    _stats(row)

    tabs = st.tabs([
        ":material/edit_note: Info & pengaturan",
        f":material/checklist: Tugas ({int(row['tasks_done'])}/{int(row['tasks_total'])})",
        f":material/inventory_2: Kebutuhan ({int(row['req_done'])}/{int(row['req_total'])})",
        f":material/report: Hambatan ({int(row['blockers_open'])})",
        f":material/folder: File kerja ({int(row['files_total'])})",
        ":material/history: Catatan & log",
    ])
    with tabs[0]:
        _info_tab(row)
    with tabs[1]:
        _tasks_tab(row)
    with tabs[2]:
        _req_tab(row)
    with tabs[3]:
        _blocker_tab(row)
    with tabs[4]:
        _files_tab(row)
    with tabs[5]:
        _log_tab(row)


# ---------------------------------------------------------------------------
# Header dan statistik
# ---------------------------------------------------------------------------
def _header(r: dict) -> None:
    gc = r["group_color"]
    badges = [
        ui.badge(r["status"], ui.STATUS_COLORS.get(r["status"], ui.MUTED)),
        ui.badge(f"Prioritas {r['priority']}", ui.PRIORITY_COLORS.get(r["priority"], ui.MUTED), "flag"),
        ui.badge(r["health"], ui.HEALTH_COLORS.get(r["health"], ui.MUTED)),
    ]
    if r.get("archived"):
        badges.append(ui.badge("Diarsipkan", ui.MUTED))
    meta = []
    if ui.has(r.get("role")):
        meta.append(f'<span>{ui.icon("user", 13)}Peran: {ui.esc(r["role"])}</span>')
    if ui.has(r.get("stakeholder")):
        meta.append(f'<span>{ui.icon("target", 13)}Stakeholder: {ui.esc(r["stakeholder"])}</span>')
    if ui.has(r.get("tags")):
        meta.append(f'<span>{ui.icon("layers", 13)}{ui.esc(r["tags"])}</span>')
    meta.append(f'<span>{ui.icon("clock", 13)}Diperbarui {relative_ts(r["updated_at"])}</span>')
    nxt = ""
    if ui.has(r.get("next_action")) and r["status"] != "Selesai":
        nxt = (f'<div class="pt-next" style="font-size:14px;margin-top:14px">{ui.icon("next", 16, ui.PRIMARY)}'
               f'<span><b>Langkah berikutnya:</b> {ui.esc(r["next_action"])}</span></div>')
    reason = ""
    if r["health"] in ("Berisiko", "Terlambat"):
        reason = (f'<div style="margin-top:10px;font-size:13px;color:{ui.HEALTH_COLORS[r["health"]]}">'
                  f'{ui.icon("alert", 13)} {ui.esc(r["health_reason"])}</div>')
    ui.html(
        f'<div class="pt-dhead" style="--gc:{gc}">{ui.group_chip(r["group_name"], gc)}'
        f'<div class="pt-dtitle">{ui.esc(r["name"])}</div>'
        f'<div class="pt-ddesc">{(ui.esc(r.get("description")) or "Belum ada deskripsi.")}</div>'
        f'<div class="pt-badges" style="margin-top:12px">{"".join(badges)}</div>'
        f'<div class="pt-meta">{"".join(meta)}</div>{reason}{nxt}</div>'
    )
    if ui.has(r.get("main_link")):
        st.link_button("Buka link proyek", r["main_link"], icon=":material/open_in_new:", type="primary")


def _stats(r: dict) -> None:
    cols = st.columns(5, gap="small")
    pct = int(r["progress_eff"])
    exp = r.get("expected")
    exp_txt = f"Ideal menurut jadwal {int(exp)}%" if pd.notna(exp) else (
        "Dari checklist tugas" if r["progress_mode"] == "auto" else "Diisi manual")
    due_sub = days_label(r["days_left"]) if r["status"] != "Selesai" else "Proyek selesai"
    items = [
        ("Progres", f"{pct}%", ui.progress_bar(pct, ui.progress_color(pct, r["health"]), label=False)
         + f'<small>{exp_txt}</small>'),
        ("Tenggat", fmt_date(r["due_date"]), f"<small>{due_sub}</small>"),
        ("Mulai", fmt_date(r["start_date"]), f"<small>Dibuat {fmt_date(r['created_at'])}</small>"),
        ("Tugas selesai", f"{int(r['tasks_done'])}/{int(r['tasks_total'])}",
         f"<small>{int(r['tasks_total'] - r['tasks_done'])} tersisa</small>"),
        ("Hambatan terbuka", int(r["blockers_open"]), f"<small>{int(r['blockers_high'])} prioritas tinggi</small>"),
    ]
    for col, (label, val, extra) in zip(cols, items):
        col.markdown(f'<div class="pt-stat"><span class="pt-label">{label}</span><b>{ui.esc(val)}</b>{extra}</div>',
                     unsafe_allow_html=True)
    st.write("")


# ---------------------------------------------------------------------------
# Tab: info & pengaturan
# ---------------------------------------------------------------------------
def _info_tab(r: dict) -> None:
    pid = int(r["id"])
    groups = db.list_groups()
    gids = [None] + groups["id"].tolist()
    glabels = {None: "Tanpa grup"} | dict(zip(groups["id"], groups["name"]))
    gid = None if pd.isna(r.get("group_id")) else int(r["group_id"])

    with st.form(f"edit_{pid}", border=False):
        name = st.text_input("Nama proyek", r["name"])
        c1, c2, c3 = st.columns(3)
        group_id = c1.selectbox("Grup / sumber", gids, index=gids.index(gid) if gid in gids else 0,
                                format_func=lambda x: glabels[x])
        status = c2.selectbox("Status", db.STATUSES, index=db.STATUSES.index(r["status"]))
        priority = c3.selectbox("Prioritas", db.PRIORITIES, index=db.PRIORITIES.index(r["priority"]))

        c4, c5, c6 = st.columns(3)
        start = c4.date_input("Tanggal mulai", value=parse_date(r["start_date"]), format="DD/MM/YYYY")
        due = c5.date_input("Tenggat", value=parse_date(r["due_date"]), format="DD/MM/YYYY")
        mode = c6.selectbox("Cara hitung progres", ["manual", "auto"], index=0 if r["progress_mode"] == "manual" else 1,
                            format_func=lambda x: "Manual" if x == "manual" else "Otomatis dari tugas")
        progress = st.slider("Progres manual (%), dipakai jika cara hitung = Manual", 0, 100, int(r["progress"] or 0), step=5,
                             help="Dipakai jika cara hitung = Manual. Jika Otomatis, progres dihitung dari checklist tugas.")
        link = st.text_input("Link utama proyek", (r.get("main_link") if ui.has(r.get("main_link")) else ""), placeholder="https://")
        desc = st.text_area("Deskripsi", (r.get("description") if ui.has(r.get("description")) else ""), height=100)
        nxt = st.text_input("Langkah berikutnya", (r.get("next_action") if ui.has(r.get("next_action")) else ""))
        c7, c8, c9 = st.columns(3)
        role = c7.text_input("Peran saya", (r.get("role") if ui.has(r.get("role")) else ""))
        stakeholder = c8.text_input("Pemberi tugas / stakeholder", (r.get("stakeholder") if ui.has(r.get("stakeholder")) else ""))
        tags = c9.text_input("Tag", (r.get("tags") if ui.has(r.get("tags")) else ""))
        c10, c11 = st.columns(2)
        pinned = c10.checkbox("Sematkan di atas papan", value=bool(r.get("pinned")))
        archived = c11.checkbox("Arsipkan proyek", value=bool(r.get("archived")),
                                help="Proyek arsip disembunyikan dari papan dan ringkasan")
        saved = st.form_submit_button("Simpan perubahan", type="primary", icon=":material/save:")

    if saved:
        if not name.strip():
            st.error("Nama proyek wajib diisi.")
        elif start and due and due < start:
            st.error("Tenggat tidak boleh lebih awal dari tanggal mulai.")
        else:
            db.update_project(pid, dict(
                name=name.strip(), group_id=group_id, status=status, priority=priority,
                start_date=start.isoformat() if start else None, due_date=due.isoformat() if due else None,
                progress_mode=mode, progress=progress, main_link=link.strip(), description=desc.strip(),
                next_action=nxt.strip(), role=role.strip(), stakeholder=stakeholder.strip(), tags=tags.strip(),
                pinned=1 if pinned else 0, archived=1 if archived else 0,
            ))
            state.flash("Perubahan disimpan")
            st.rerun()

    st.divider()
    with st.expander("Hapus proyek", icon=":material/delete:"):
        st.warning("Menghapus proyek juga menghapus tugas, kebutuhan, hambatan, file kerja, dan log. Tidak bisa dibatalkan. "
                   "Jika hanya ingin menyembunyikan, gunakan opsi Arsipkan.", icon=":material/warning:")
        confirm = st.text_input("Ketik HAPUS untuk konfirmasi", key=f"del_confirm_{pid}")
        if st.button("Hapus permanen", key=f"del_{pid}", disabled=confirm.strip() != "HAPUS", icon=":material/delete_forever:"):
            db.delete_project(pid)
            st.session_state.pop("selected_project", None)
            st.query_params.clear()
            state.flash(f"Proyek \"{r['name']}\" dihapus", "warning")
            st.rerun()


# ---------------------------------------------------------------------------
# Helper data_editor
# ---------------------------------------------------------------------------
def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date.astype(object).where(lambda s: pd.notna(s), None)


def _iso(value) -> str | None:
    d = parse_date(value)
    return d.isoformat() if isinstance(d, date) else None


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _editor(df: pd.DataFrame, key: str, config: dict, order: list[str]) -> pd.DataFrame:
    return st.data_editor(
        df, key=key, num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"id": None, **config}, column_order=order,
    )


# ---------------------------------------------------------------------------
# Tab: tugas
# ---------------------------------------------------------------------------
def _tasks_tab(r: dict) -> None:
    pid = int(r["id"])
    df = db.get_children(pid, "tasks")
    df["done"] = df["done"].astype(bool)
    df["due_date"] = _to_date(df["due_date"])
    if r["progress_mode"] == "auto":
        st.caption("Progres proyek ini dihitung otomatis dari persentase tugas yang dicentang.")
    else:
        st.caption("Progres proyek ini diisi manual. Ubah ke Otomatis di tab Info jika ingin progres mengikuti checklist.")
    edited = _editor(df, f"tasks_{pid}", {
        "done": st.column_config.CheckboxColumn("Selesai", width="small", default=False),
        "title": st.column_config.TextColumn("Tugas", width="large", required=True),
        "due_date": st.column_config.DateColumn("Tenggat", format="DD/MM/YYYY", width="small"),
    }, ["done", "title", "due_date"])

    if st.button("Simpan tugas", key=f"save_tasks_{pid}", type="primary", icon=":material/save:"):
        recs = []
        for i, row in enumerate(edited.to_dict("records")):
            title = _clean(row.get("title"))
            if not title:
                continue
            recs.append({"title": title, "done": 1 if row.get("done") else 0, "due_date": _iso(row.get("due_date")), "sort": i})
        before = int(r["tasks_done"])
        after = sum(x["done"] for x in recs)
        msg = f"Checklist diperbarui: {after}/{len(recs)} tugas selesai" + (f" (+{after - before})" if after > before else "")
        with st.spinner("Menyimpan..."):
            db.replace_children(pid, "tasks", recs, note=("tugas", msg))
        state.flash("Tugas disimpan")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: kebutuhan
# ---------------------------------------------------------------------------
def _req_tab(r: dict) -> None:
    pid = int(r["id"])
    df = db.get_children(pid, "requirements")
    st.caption("Catat apa saja yang dibutuhkan agar proyek bisa jalan: data, akses, tools, anggaran, persetujuan, SDM.")
    edited = _editor(df, f"req_{pid}", {
        "item": st.column_config.TextColumn("Kebutuhan", width="large", required=True),
        "category": st.column_config.SelectboxColumn("Kategori", options=db.REQ_CATEGORIES, default="Lainnya", width="small"),
        "status": st.column_config.SelectboxColumn("Status", options=db.REQ_STATUSES, default="Belum ada", width="small"),
        "notes": st.column_config.TextColumn("Catatan", width="medium"),
    }, ["item", "category", "status", "notes"])
    if st.button("Simpan kebutuhan", key=f"save_req_{pid}", type="primary", icon=":material/save:"):
        recs = []
        for row in edited.to_dict("records"):
            item = _clean(row.get("item"))
            if not item:
                continue
            recs.append({"item": item, "category": row.get("category") or "Lainnya",
                         "status": row.get("status") or "Belum ada", "notes": _clean(row.get("notes"))})
        done = sum(1 for x in recs if x["status"] == "Terpenuhi")
        with st.spinner("Menyimpan..."):
            db.replace_children(pid, "requirements", recs,
                                note=("kebutuhan", f"Kebutuhan diperbarui: {done}/{len(recs)} terpenuhi"))
        state.flash("Kebutuhan disimpan")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: hambatan
# ---------------------------------------------------------------------------
def _blocker_tab(r: dict) -> None:
    pid = int(r["id"])
    df = db.get_children(pid, "blockers")
    df["raised_at"] = _to_date(df["raised_at"])
    df["resolved_at"] = _to_date(df["resolved_at"])
    st.caption("Ubah status ke Selesai saat hambatan teratasi. Tanggal selesai terisi otomatis jika dikosongkan.")
    edited = _editor(df, f"blk_{pid}", {
        "description": st.column_config.TextColumn("Hambatan", width="large", required=True),
        "severity": st.column_config.SelectboxColumn("Tingkat", options=db.BLOCKER_SEVERITIES, default="Sedang", width="small"),
        "status": st.column_config.SelectboxColumn("Status", options=db.BLOCKER_STATUSES, default="Terbuka", width="small"),
        "raised_at": st.column_config.DateColumn("Muncul", format="DD/MM/YYYY", default=today(), width="small"),
        "resolved_at": st.column_config.DateColumn("Teratasi", format="DD/MM/YYYY", width="small"),
        "resolution": st.column_config.TextColumn("Solusi / tindak lanjut", width="medium"),
    }, ["description", "severity", "status", "raised_at", "resolved_at", "resolution"])
    if st.button("Simpan hambatan", key=f"save_blk_{pid}", type="primary", icon=":material/save:"):
        recs = []
        for row in edited.to_dict("records"):
            desc = _clean(row.get("description"))
            if not desc:
                continue
            status = row.get("status") or "Terbuka"
            resolved = _iso(row.get("resolved_at"))
            if status == "Selesai" and not resolved:
                resolved = today().isoformat()
            if status == "Terbuka":
                resolved = None
            recs.append({"description": desc, "severity": row.get("severity") or "Sedang", "status": status,
                         "raised_at": _iso(row.get("raised_at")) or today().isoformat(),
                         "resolved_at": resolved, "resolution": _clean(row.get("resolution"))})
        n_open = sum(1 for x in recs if x["status"] == "Terbuka")
        with st.spinner("Menyimpan..."):
            db.replace_children(pid, "blockers", recs,
                                note=("hambatan", f"Hambatan diperbarui: {n_open} terbuka dari {len(recs)}"))
        state.flash("Hambatan disimpan")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: file kerja
# ---------------------------------------------------------------------------
def _files_tab(r: dict) -> None:
    pid = int(r["id"])
    df = db.get_children(pid, "files")
    if not df.empty:
        st.markdown('<div class="pt-label" style="margin-bottom:8px">Akses cepat</div>', unsafe_allow_html=True)
        cols = st.columns(3, gap="small")
        for i, f in enumerate(df.to_dict("records")):
            color, ico = FILE_ICON.get(f["ftype"], FILE_ICON["Lainnya"])
            url = f["url"] or "#"
            target = ' target="_blank" rel="noopener"' if f["url"] else ""
            notes = ui.esc(f["notes"]) if f["notes"] else ui.esc(f["ftype"])
            cols[i % 3].markdown(
                f'<a class="pt-file" href="{ui.esc(url)}"{target}>'
                f'<span class="pt-file-ico" style="background:{ui.tint(color)};color:{color}">{ui.icon(ico, 16)}</span>'
                f'<span style="min-width:0"><span style="display:block;font-weight:650;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{ui.esc(f["name"])}</span>'
                f'<span style="display:block;font-size:12px;color:{ui.MUTED};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{notes}</span></span>'
                f'<span style="margin-left:auto;color:{ui.FAINT}">{ui.icon("arrow", 14)}</span></a>',
                unsafe_allow_html=True,
            )
        st.write("")
    st.caption("Simpan semua link kerja: spreadsheet, dokumen, deck, dashboard, repo, folder Drive.")
    df["added_at"] = _to_date(df["added_at"])
    edited = _editor(df, f"files_{pid}", {
        "name": st.column_config.TextColumn("Nama file", width="medium", required=True),
        "url": st.column_config.LinkColumn("URL", width="large", validate=r"^https?://.+", display_text=None),
        "ftype": st.column_config.SelectboxColumn("Jenis", options=db.FILE_TYPES, default="Dokumen", width="small"),
        "notes": st.column_config.TextColumn("Catatan", width="medium"),
        "added_at": st.column_config.DateColumn("Ditambahkan", format="DD/MM/YYYY", default=today(), width="small"),
    }, ["name", "url", "ftype", "notes", "added_at"])
    if st.button("Simpan file kerja", key=f"save_files_{pid}", type="primary", icon=":material/save:"):
        recs = []
        for row in edited.to_dict("records"):
            name = _clean(row.get("name"))
            if not name:
                continue
            recs.append({"name": name, "url": _clean(row.get("url")), "ftype": row.get("ftype") or "Lainnya",
                         "notes": _clean(row.get("notes")), "added_at": _iso(row.get("added_at")) or today().isoformat()})
        with st.spinner("Menyimpan..."):
            db.replace_children(pid, "files", recs, note=("file", f"Daftar file kerja diperbarui ({len(recs)} file)"))
        state.flash("File kerja disimpan")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: catatan & log
# ---------------------------------------------------------------------------
def _log_tab(r: dict) -> None:
    pid = int(r["id"])
    with st.form(f"note_{pid}", clear_on_submit=True, border=False):
        note = st.text_area("Tambah catatan", placeholder="Hasil rapat, keputusan, update progres, ide...", height=90)
        if st.form_submit_button("Simpan catatan", type="primary", icon=":material/add_comment:") and note.strip():
            db.add_activity(pid, "catatan", note.strip())
            db.touch_project(pid)
            state.flash("Catatan ditambahkan")
            st.rerun()

    log = db.project_activity(pid)
    if log.empty:
        st.caption("Belum ada catatan.")
        return
    only_notes = st.toggle("Hanya catatan", key=f"only_notes_{pid}")
    if only_notes:
        log = log[log["kind"] == "catatan"]
    colors = {"catatan": ui.PRIMARY, "status": "#7C3AED", "progres": "#2563EB", "dibuat": ui.ACCENT,
              "hambatan": ui.HEALTH_COLORS["Terlambat"], "tenggat": ui.HEALTH_COLORS["Berisiko"]}
    items = []
    for _, a in log.iterrows():
        kind_label = "Catatan" if a["kind"] == "catatan" else a["kind"].capitalize()
        msg = ui.esc(a["message"]).replace("\n", "<br>")
        items.append(
            f'<div class="pt-tl-item" style="--c:{colors.get(a["kind"], ui.FAINT)}">'
            f'<div class="pt-tl-msg">{msg}</div>'
            f'<div class="pt-tl-ts">{kind_label} · {fmt_ts(a["ts"])}</div></div>'
        )
    ui.html(f'<div class="pt-kpi" style="margin-top:8px"><div class="pt-tl">{"".join(items)}</div></div>')
