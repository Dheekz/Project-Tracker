"""Halaman Ringkasan: gambaran cepat seluruh pekerjaan."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import db, logic, ui
from core.timeutil import days_label, fmt_date, fmt_day_long, relative_ts, today


def render() -> None:
    df_all = logic.load_projects()
    ui.page_header(
        "Ringkasan pekerjaan",
        "Posisi semua proyek, yang perlu perhatian, dan tenggat terdekat dalam satu layar.",
        eyebrow=fmt_day_long(today()),
    )

    groups = sorted(df_all["group_name"].dropna().unique().tolist()) if not df_all.empty else []
    picked = st.pills("Filter grup", groups, selection_mode="multi", key="dash_groups",
                      label_visibility="collapsed") if groups else []
    df = df_all[df_all["group_name"].isin(picked)] if picked else df_all

    s = logic.summary(df)
    ui.html(f'<div class="pt-banner">{logic.narrative(s)}</div>')

    if df.empty:
        st.info("Belum ada proyek untuk ditampilkan.", icon=":material/info:")
        return

    _kpis(s)
    _health_strip(df)

    c1, c2 = st.columns([1.35, 1], gap="medium")
    with c1:
        ui.section("Progres per grup", "rata-rata proyek yang belum selesai")
        _group_progress_chart(df)
    with c2:
        ui.section("Distribusi status", f"{len(df)} proyek")
        _status_donut(df)

    c3, c4 = st.columns(2, gap="medium")
    with c3:
        _attention_list(df)
    with c4:
        _deadline_list(df)

    _timeline(df)
    _group_cards(df)

    c5, c6 = st.columns(2, gap="medium")
    with c5:
        _open_blockers(df)
    with c6:
        _pending_requirements(df)

    _activity()


# ---------------------------------------------------------------------------
def _kpis(s: dict) -> None:
    cols = st.columns(5, gap="small")
    attention = s["late"] + s["risk"]
    cards = [
        ("Proyek aktif", s["active"], f"{s['ideas']} ide · {s['paused']} tertunda", ui.PRIMARY, "layers"),
        ("Rata-rata progres", f"{s['avg_progress']}%", "dari proyek aktif", "#2563EB", "target"),
        ("Perlu perhatian", attention, f"{s['late']} terlambat · {s['risk']} berisiko",
         ui.HEALTH_COLORS["Terlambat"] if s["late"] else ui.HEALTH_COLORS["Berisiko"], "alert"),
        ("Hambatan terbuka", s["blockers"], f"{s['blockers_high']} prioritas tinggi", ui.ACCENT, "flag"),
        ("Selesai", s["done"], f"{s['done_30']} dalam 30 hari terakhir", ui.HEALTH_COLORS["Aman"], "done"),
    ]
    for col, (label, val, sub, color, ico) in zip(cols, cards):
        col.markdown(ui.kpi(label, val, ui.esc(sub), color, ico), unsafe_allow_html=True)


def _health_strip(df: pd.DataFrame) -> None:
    open_ = df[df["status"] != "Selesai"]
    if open_.empty:
        return
    counts = open_["health"].value_counts()
    total = len(open_)
    segs, legend = [], []
    for h in ["Aman", "Berisiko", "Terlambat"]:
        n = int(counts.get(h, 0))
        if n:
            segs.append(f'<span title="{h}: {n}" style="width:{n / total * 100:.2f}%;background:{ui.HEALTH_COLORS[h]}"></span>')
        legend.append(f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px">'
                      f'<i class="pt-dot" style="background:{ui.HEALTH_COLORS[h]}"></i>{h} <b style="color:{ui.INK}">{n}</b></span>')
    ui.html(
        '<div style="margin-top:14px" class="pt-kpi">'
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
        f'<span class="pt-label">Kesehatan {total} proyek terbuka</span>'
        f'<span style="font-size:13px;color:{ui.MUTED}">{"".join(legend)}</span></div>'
        f'<div style="display:flex;height:10px;border-radius:99px;overflow:hidden;margin-top:12px;gap:2px;background:#ECEAE4">{"".join(segs)}</div>'
        '</div>'
    )


def _group_progress_chart(df: pd.DataFrame) -> None:
    g = logic.by_group(df).sort_values("avg_progress")
    fig = go.Figure(go.Bar(
        x=g["avg_progress"], y=g["group_name"], orientation="h",
        marker=dict(color=g["group_color"].tolist(), cornerradius=6),
        text=[f"{p}%  ·  {o} terbuka" for p, o in zip(g["avg_progress"], g["open"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Rata-rata progres %{x}%<extra></extra>",
        width=0.55,
    ))
    fig.update_xaxes(range=[0, 125], ticksuffix="%", tickvals=[0, 25, 50, 75, 100])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    ui.style_fig(fig, height=max(220, 70 * len(g) + 40))
    st.plotly_chart(fig, config=ui.CHART_CONFIG, width="stretch")


def _status_donut(df: pd.DataFrame) -> None:
    counts = df["status"].value_counts().reindex(db.STATUSES).fillna(0).astype(int)
    counts = counts[counts > 0]
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.66, sort=False,
        marker=dict(colors=[ui.STATUS_COLORS[s] for s in counts.index], line=dict(color="white", width=2)),
        textinfo="none", hovertemplate="<b>%{label}</b><br>%{value} proyek (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b style='font-size:28px'>{len(df)}</b><br><span style='color:{ui.MUTED}'>proyek</span>",
                       showarrow=False, font=dict(family=ui.FONT, size=13, color=ui.INK))
    ui.style_fig(fig, height=290, legend=True)
    fig.update_layout(legend=dict(orientation="v", y=0.5, yanchor="middle", x=1.02, xanchor="left"))
    st.plotly_chart(fig, config=ui.CHART_CONFIG, width="stretch")


def _attention_list(df: pd.DataFrame) -> None:
    att = df[(df["status"] != "Selesai") & (df["health"].isin(["Terlambat", "Berisiko"]))].copy()
    att["_rank"] = att["health"].map({"Terlambat": 0, "Berisiko": 1})
    att = att.sort_values(["_rank", "days_left"], na_position="last")
    ui.section("Perlu perhatian", f"{len(att)} proyek")
    rows = []
    for _, r in att.head(8).iterrows():
        color = ui.HEALTH_COLORS[r["health"]]
        sub = f'{ui.esc(r["group_name"])} · {ui.esc(r["health_reason"])}'
        end = (f'{ui.badge(r["health"], color)}<div style="margin-top:4px">{int(r["progress_eff"])}%</div>')
        rows.append(ui.list_row(r["name"], sub, end, color, ui.detail_href(r["id"])))
    ui.html(ui.list_box(rows, "Tidak ada proyek yang berisiko. Pertahankan ritmenya."))


def _deadline_list(df: pd.DataFrame) -> None:
    up = df[(df["status"] != "Selesai") & df["days_left"].notna() & (df["days_left"] >= 0) & (df["days_left"] <= 14)]
    up = up.sort_values("days_left")
    ui.section("Tenggat 14 hari ke depan", f"{len(up)} proyek")
    rows = []
    for _, r in up.head(8).iterrows():
        dl = int(r["days_left"])
        color = ui.HEALTH_COLORS["Terlambat"] if dl <= 2 else (ui.HEALTH_COLORS["Berisiko"] if dl <= 7 else ui.PRIMARY)
        sub = f'{ui.esc(r["group_name"])} · progres {int(r["progress_eff"])}%'
        end = f'<b style="color:{color}">{days_label(dl)}</b><div style="margin-top:4px">{fmt_date(r["due_date"])}</div>'
        rows.append(ui.list_row(r["name"], sub, end, r["group_color"], ui.detail_href(r["id"])))
    ui.html(ui.list_box(rows, "Tidak ada tenggat dalam 14 hari ke depan."))


def _timeline(df: pd.DataFrame) -> None:
    tl = df[(df["status"] != "Selesai") & df["due_date"].notna()].copy()
    ui.section("Lini waktu proyek terbuka", "batang = mulai sampai tenggat, garis = hari ini")
    if tl.empty:
        ui.html(ui.list_box([], "Isi tanggal mulai dan tenggat agar proyek tampil di lini waktu."))
        return
    tl["mulai"] = pd.to_datetime(tl["start_date"].fillna(tl["created_at"].str[:10]), errors="coerce")
    tl["tenggat"] = pd.to_datetime(tl["due_date"], errors="coerce")
    tl.loc[tl["tenggat"] <= tl["mulai"], "tenggat"] = tl["mulai"] + pd.Timedelta(days=1)
    tl["label"] = tl["progress_eff"].astype(int).astype(str) + "%"
    tl = tl.sort_values(["group_name", "tenggat"])
    cmap = dict(zip(tl["group_name"], tl["group_color"]))
    fig = px.timeline(
        tl, x_start="mulai", x_end="tenggat", y="name", color="group_name", text="label",
        color_discrete_map=cmap,
        custom_data=["group_name", "status", "health", "label"],
    )
    fig.update_traces(
        marker=dict(cornerradius=6), textposition="inside", insidetextanchor="start",
        textfont=dict(color="white", size=12),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}<br>"
                      "Progres %{customdata[3]}<br>%{base|%d %b %Y} sampai %{x|%d %b %Y}<extra></extra>",
    )
    t = pd.Timestamp(today())
    fig.add_shape(type="line", x0=t, x1=t, y0=0, y1=1, yref="paper", line=dict(color=ui.ACCENT, width=2, dash="dot"))
    fig.add_annotation(x=t, y=1, yref="paper", text="Hari ini", showarrow=False, yshift=10,
                       font=dict(color=ui.ACCENT, size=12, family=ui.FONT))
    fig.update_yaxes(autorange="reversed", title=None, gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(title=None, tickformat="%d %b")
    ui.style_fig(fig, height=max(260, 42 * len(tl) + 90), legend=True)
    fig.update_layout(legend_title_text="", margin=dict(t=28))
    st.plotly_chart(fig, config=ui.CHART_CONFIG, width="stretch")


def _group_cards(df: pd.DataFrame) -> None:
    g = logic.by_group(df)
    ui.section("Per grup / sumber", f"{len(g)} grup")
    per_row = 4
    for start in range(0, len(g), per_row):
        cols = st.columns(per_row, gap="small")
        for col, (_, r) in zip(cols, g.iloc[start:start + per_row].iterrows()):
            warn = ""
            if r["late"] or r["risk"]:
                n_att = int(r["late"] + r["risk"])
                warn_badge = ui.badge(f"{n_att} perlu perhatian", ui.HEALTH_COLORS["Berisiko"], "alert")
                warn = f'<div style="margin-top:10px">{warn_badge}</div>'
            col.markdown(
                f'<div class="pt-gcard" style="--gc:{r["group_color"]}">'
                f'<div class="pt-gcard-name">{ui.esc(r["group_name"])}</div>'
                f'<div class="pt-gstats"><div><b>{r["open"]}</b>terbuka</div><div><b>{r["done"]}</b>selesai</div>'
                f'<div><b>{r["blockers"]}</b>hambatan</div></div>'
                f'<div style="margin-top:12px">{ui.progress_bar(r["avg_progress"], r["group_color"])}</div>{warn}</div>',
                unsafe_allow_html=True,
            )


def _open_blockers(df: pd.DataFrame) -> None:
    b = db.all_children("blockers")
    b = b[(b["status"] == "Terbuka") & (b["project_id"].isin(df["id"]))].copy()
    sev_rank = {"Kritis": 0, "Tinggi": 1, "Sedang": 2, "Rendah": 3}
    b["_r"] = b["severity"].map(sev_rank)
    b = b.sort_values(["_r", "raised_at"])
    ui.section("Hambatan terbuka", f"{len(b)} item")
    rows = []
    for _, r in b.head(8).iterrows():
        color = ui.PRIORITY_COLORS.get(r["severity"], ui.MUTED)
        age = ""
        if r["raised_at"]:
            days = (today() - pd.to_datetime(r["raised_at"]).date()).days
            age = f"{days} hari"
        rows.append(ui.list_row(r["description"], ui.esc(r["project_name"]),
                                f'{ui.badge(r["severity"], color)}<div style="margin-top:4px">{age}</div>',
                                color, ui.detail_href(r["project_id"])))
    ui.html(ui.list_box(rows, "Tidak ada hambatan terbuka."))


def _pending_requirements(df: pd.DataFrame) -> None:
    q = db.all_children("requirements")
    q = q[(q["status"] != "Terpenuhi") & (q["project_id"].isin(df["id"])) & (q["project_status"] != "Selesai")]
    q = q.sort_values("status")
    ui.section("Kebutuhan belum terpenuhi", f"{len(q)} item")
    rows = []
    for _, r in q.head(8).iterrows():
        color = ui.REQ_COLORS.get(r["status"], ui.MUTED)
        rows.append(ui.list_row(r["item"], f'{ui.esc(r["project_name"])} · {ui.esc(r["category"])}',
                                ui.badge(r["status"], color), color, ui.detail_href(r["project_id"])))
    ui.html(ui.list_box(rows, "Semua kebutuhan sudah terpenuhi."))


def _activity() -> None:
    act = db.recent_activity(10)
    ui.section("Aktivitas terbaru", "")
    if act.empty:
        ui.html(ui.list_box([], "Belum ada aktivitas."))
        return
    items = []
    for _, r in act.iterrows():
        items.append(
            f'<div class="pt-tl-item" style="--c:{r["group_color"] or ui.FAINT}">'
            f'<div class="pt-tl-msg"><a href="{ui.detail_href(r["project_id"])}" target="_self" '
            f'style="color:{ui.INK};font-weight:650;text-decoration:none">{ui.esc(r["project_name"])}</a>'
            f' · {ui.esc(r["message"])}</div><div class="pt-tl-ts">{relative_ts(r["ts"])}</div></div>'
        )
    ui.html(f'<div class="pt-kpi"><div class="pt-tl">{"".join(items)}</div></div>')
