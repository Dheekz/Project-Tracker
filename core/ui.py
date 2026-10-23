"""Token desain, CSS global, dan komponen HTML kecil.

Arah visual "Quiet Ledger": kanvas kertas yang tenang, tipografi tegas,
garis tipis 1px, tanpa bayangan berat. Warna dipakai sebagai informasi
(grup, status, kesehatan), bukan dekorasi.
"""
from __future__ import annotations

import math
from html import escape

import plotly.graph_objects as go
import streamlit as st

from core.timeutil import days_label, fmt_date

# ---------------------------------------------------------------------------
# Token warna
# ---------------------------------------------------------------------------
INK = "#0F172A"
MUTED = "#5B6474"
FAINT = "#94A3B8"
LINE = "#E6E4DF"
PAPER = "#F6F5F1"
CARD = "#FFFFFF"
PRIMARY = "#0F766E"
ACCENT = "#EA580C"

STATUS_COLORS = {
    "Ide": "#64748B",
    "To Do": "#2563EB",
    "Berjalan": "#0F766E",
    "Review": "#7C3AED",
    "Tertunda": "#B45309",
    "Selesai": "#15803D",
}
PRIORITY_COLORS = {"Rendah": "#64748B", "Sedang": "#2563EB", "Tinggi": "#C2410C", "Kritis": "#DC2626"}
PRIORITY_RANK = {"Kritis": 0, "Tinggi": 1, "Sedang": 2, "Rendah": 3}
HEALTH_COLORS = {"Aman": "#15803D", "Berisiko": "#B45309", "Terlambat": "#DC2626", "Selesai": "#475569"}
REQ_COLORS = {"Belum ada": "#DC2626", "Diproses": "#B45309", "Terpenuhi": "#15803D"}
GROUP_PALETTE = ["#0F766E", "#2563EB", "#EA580C", "#7C3AED", "#DB2777", "#0891B2", "#65A30D", "#475569"]

FONT = "Plus Jakarta Sans, sans-serif"

# ---------------------------------------------------------------------------
# Ikon SVG (gaya Lucide, stroke mengikuti warna teks)
# ---------------------------------------------------------------------------
_ICONS = {
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "check": '<path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
    "clip": '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "pulse": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "done": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    "arrow": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "box": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "pin": '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
    "next": '<circle cx="12" cy="12" r="10"/><path d="m10 8 4 4-4 4"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
}


def icon(name: str, size: int = 14, color: str = "currentColor") -> str:
    paths = _ICONS.get(name, "")
    return (
        f'<svg aria-hidden="true" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:-2px;flex-shrink:0">{paths}</svg>'
    )


# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------
CSS = f"""
<style>
:root {{
  --pt-ink:{INK}; --pt-muted:{MUTED}; --pt-faint:{FAINT}; --pt-line:{LINE};
  --pt-paper:{PAPER}; --pt-card:{CARD}; --pt-primary:{PRIMARY}; --pt-accent:{ACCENT};
}}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1480px; }}
[data-testid="stSidebar"] {{ border-right: 1px solid var(--pt-line); }}
[data-testid="stSidebarNavSeparator"] {{ border-color: var(--pt-line); }}

/* Kartu bordered container dengan key berawalan card / panel */
div[class*="st-key-card_"], div[class*="st-key-panel_"] {{
  background: var(--pt-card); border-radius: 14px;
  transition: border-color .15s ease, transform .15s ease;
}}
div[class*="st-key-card_"]:hover {{ border-color: #CBD5E1; }}
div[class*="st-key-card_"] [data-testid="stButton"] button,
div[class*="st-key-card_"] [data-testid="stPopover"] button {{
  min-height: 34px; padding: 2px 10px; font-size: 13px;
}}

/* Header halaman */
.pt-eyebrow {{ font-size: 12px; font-weight: 600; letter-spacing: .09em; text-transform: uppercase; color: var(--pt-primary); margin-bottom: 6px; }}
.pt-title {{ font-size: 30px; line-height: 1.15; font-weight: 750; letter-spacing: -0.02em; color: var(--pt-ink); margin: 0; }}
.pt-sub {{ font-size: 15px; color: var(--pt-muted); margin: 6px 0 0 0; max-width: 760px; }}
.pt-head {{ margin-bottom: 18px; }}

/* Label kecil gaya katalog */
.pt-label {{ font-size: 11.5px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--pt-muted); }}
.pt-section {{ display:flex; align-items:baseline; justify-content:space-between; margin: 26px 0 10px 0; gap: 12px; }}
.pt-section h3 {{ font-size: 17px; font-weight: 700; margin: 0; padding: 0; color: var(--pt-ink); letter-spacing: -0.01em; }}
.pt-section span {{ font-size: 13px; color: var(--pt-muted); }}

/* Banner ringkasan */
.pt-banner {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-left: 4px solid var(--pt-primary);
  border-radius: 12px; padding: 14px 18px; font-size: 15px; line-height: 1.6; color: var(--pt-ink); margin-bottom: 16px; }}

/* KPI */
.pt-kpi {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-radius: 14px; padding: 16px 18px 14px; height: 100%; }}
.pt-kpi-top {{ display:flex; align-items:center; justify-content:space-between; }}
.pt-kpi-ico {{ width: 30px; height: 30px; border-radius: 9px; display:flex; align-items:center; justify-content:center; }}
.pt-kpi-val {{ font-size: 32px; font-weight: 750; letter-spacing: -0.03em; color: var(--pt-ink); margin-top: 10px; line-height: 1; }}
.pt-kpi-sub {{ font-size: 13px; color: var(--pt-muted); margin-top: 8px; }}

/* Badge dan chip */
.pt-badge {{ display:inline-flex; align-items:center; gap:5px; font-size: 12px; font-weight: 650; padding: 3px 9px;
  border-radius: 999px; white-space: nowrap; line-height: 1.4; }}
.pt-gchip {{ display:inline-flex; align-items:center; gap:6px; font-size: 12px; font-weight: 600; color: var(--pt-muted);
  max-width: 100%; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }}
.pt-gchip i {{ width: 8px; height: 8px; border-radius: 2px; display:inline-block; flex-shrink:0; }}
.pt-badges {{ display:flex; flex-wrap:wrap; gap:6px; margin: 8px 0 10px; }}

/* Progress */
.pt-prog {{ height: 6px; background: #ECEAE4; border-radius: 99px; overflow: hidden; flex: 1; }}
.pt-prog > span {{ display:block; height:100%; border-radius: 99px; }}
.pt-prog-row {{ display:flex; align-items:center; gap: 10px; font-size: 12.5px; font-weight: 700; color: var(--pt-ink); }}

/* Kartu proyek kanban */
.pt-pcard-top {{ display:flex; justify-content:space-between; align-items:center; gap: 6px; }}
.pt-pcard-title {{ font-size: 15px; font-weight: 700; color: var(--pt-ink); line-height: 1.35; margin-top: 8px; letter-spacing: -0.01em; }}
.pt-meta {{ display:flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; font-size: 12.5px; color: var(--pt-muted); }}
.pt-meta span {{ display:inline-flex; align-items:center; gap: 4px; }}
.pt-next {{ margin-top: 10px; padding-top: 9px; border-top: 1px dashed var(--pt-line); font-size: 12.5px; color: var(--pt-ink);
  display:flex; gap:6px; align-items:flex-start; line-height:1.45; margin-bottom: 6px; }}

/* Kolom kanban */
.pt-col-head {{ display:flex; align-items:center; justify-content:space-between; padding: 10px 12px; border-radius: 12px;
  background: var(--pt-card); border: 1px solid var(--pt-line); margin-bottom: 10px; border-top-width: 3px; }}
.pt-col-head b {{ font-size: 14px; font-weight: 700; color: var(--pt-ink); }}
.pt-count {{ font-size: 12px; font-weight: 700; color: var(--pt-muted); background: #F1F0EC; border-radius: 999px; padding: 2px 9px; }}
.pt-empty {{ border: 1.5px dashed #D9D6CE; border-radius: 12px; padding: 18px 10px; text-align:center; font-size: 13px; color: var(--pt-faint); }}

/* Daftar ringkas (perhatian, tenggat, aktivitas) */
.pt-list {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-radius: 14px; overflow: hidden; }}
.pt-row {{ display:flex; align-items:center; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #F0EEE9; text-decoration:none !important; color: inherit !important; }}
.pt-row:last-child {{ border-bottom: none; }}
a.pt-row:hover {{ background: #FAF9F6; }}
.pt-row-main {{ flex: 1; min-width: 0; }}
.pt-row-title {{ font-size: 14px; font-weight: 650; color: var(--pt-ink); white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }}
.pt-row-sub {{ font-size: 12.5px; color: var(--pt-muted); margin-top: 2px; white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }}
.pt-row-end {{ text-align:right; font-size: 12.5px; color: var(--pt-muted); white-space: nowrap; }}
.pt-bar {{ width: 4px; align-self: stretch; border-radius: 4px; flex-shrink:0; }}
.pt-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink:0; }}

/* Kartu grup */
.pt-gcard {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-radius: 14px; padding: 16px 18px; height: 100%; position: relative; overflow: hidden; }}
.pt-gcard:before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background: var(--gc); }}
.pt-gcard-name {{ font-size: 15px; font-weight: 700; color: var(--pt-ink); line-height: 1.3; }}
.pt-gcard-kind {{ font-size: 12px; color: var(--pt-muted); margin-top: 2px; }}
.pt-gstats {{ display:flex; gap: 18px; margin-top: 14px; }}
.pt-gstats div {{ font-size: 12px; color: var(--pt-muted); }}
.pt-gstats b {{ display:block; font-size: 20px; color: var(--pt-ink); font-weight: 750; letter-spacing:-0.02em; }}

/* Header detail proyek */
.pt-dhead {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-radius: 16px; padding: 20px 22px; margin-bottom: 14px; position: relative; overflow:hidden; }}
.pt-dhead:before {{ content:""; position:absolute; left:0; right:0; top:0; height:4px; background: var(--gc); }}
.pt-dtitle {{ font-size: 26px; font-weight: 750; letter-spacing: -0.02em; color: var(--pt-ink); margin: 8px 0 4px; line-height:1.2; }}
.pt-ddesc {{ font-size: 14.5px; color: var(--pt-muted); max-width: 900px; line-height: 1.55; }}
.pt-stat {{ background: var(--pt-card); border: 1px solid var(--pt-line); border-radius: 12px; padding: 12px 14px; }}
.pt-stat b {{ display:block; font-size: 20px; font-weight: 750; color: var(--pt-ink); margin-top: 4px; letter-spacing:-0.02em; }}
.pt-stat small {{ font-size: 12px; color: var(--pt-muted); }}

/* File kerja */
.pt-file {{ display:flex; align-items:center; gap:10px; background: var(--pt-card); border:1px solid var(--pt-line); border-radius: 12px;
  padding: 10px 12px; text-decoration:none !important; color: var(--pt-ink) !important; margin-bottom: 8px; transition: border-color .15s ease; }}
.pt-file:hover {{ border-color: var(--pt-primary); }}
.pt-file-ico {{ width: 32px; height: 32px; border-radius: 9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}

/* Timeline aktivitas */
.pt-tl {{ position: relative; padding-left: 18px; }}
.pt-tl-item {{ position: relative; padding: 0 0 14px 6px; }}
.pt-tl-item:before {{ content:""; position:absolute; left:-14px; top:5px; width:9px; height:9px; border-radius:50%; background: var(--c); }}
.pt-tl-item:after {{ content:""; position:absolute; left:-10px; top:16px; bottom:0; width:1px; background: var(--pt-line); }}
.pt-tl-item:last-child:after {{ display:none; }}
.pt-tl-msg {{ font-size: 14px; color: var(--pt-ink); line-height: 1.45; }}
.pt-tl-ts {{ font-size: 12px; color: var(--pt-muted); }}

/* Sidebar */
.pt-side-stat {{ display:flex; justify-content:space-between; font-size: 13px; color: var(--pt-muted); padding: 5px 2px; }}
.pt-side-stat b {{ color: var(--pt-ink); }}

/* Fokus keyboard tetap terlihat */
a:focus-visible, button:focus-visible {{ outline: 2px solid var(--pt-primary) !important; outline-offset: 2px; }}

@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
@media (max-width: 640px) {{ .pt-title {{ font-size: 24px; }} .pt-kpi-val {{ font-size: 26px; }} }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def esc(value) -> str:
    return escape(str(value)) if has(value) else ""


def has(value) -> bool:
    """True jika nilai terisi (bukan None, NaN, atau string kosong)."""
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() not in ("", "nan", "None", "NaT")


# ---------------------------------------------------------------------------
# Komponen
# ---------------------------------------------------------------------------
def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    parts = ['<div class="pt-head">']
    if eyebrow:
        parts.append(f'<div class="pt-eyebrow">{esc(eyebrow)}</div>')
    parts.append(f'<h1 class="pt-title">{esc(title)}</h1>')
    if subtitle:
        parts.append(f'<p class="pt-sub">{esc(subtitle)}</p>')
    parts.append("</div>")
    html("".join(parts))


def section(title: str, note: str = "") -> None:
    html(f'<div class="pt-section"><h3>{esc(title)}</h3><span>{esc(note)}</span></div>')


def tint(color: str, alpha: str = "1A") -> str:
    return f"{color}{alpha}" if color and color.startswith("#") and len(color) == 7 else color


def badge(text: str, color: str, ico: str | None = None) -> str:
    ic = icon(ico, 12) if ico else ""
    return f'<span class="pt-badge" style="background:{tint(color)};color:{color}">{ic}{esc(text)}</span>'


def group_chip(name: str, color: str) -> str:
    return (f'<span class="pt-gchip"><i style="background:{color}"></i>'
            f'<span style="overflow:hidden;text-overflow:ellipsis">{esc(name)}</span></span>')


def progress_bar(pct, color: str = PRIMARY, label: bool = True) -> str:
    pct = int(pct or 0)
    lab = f"<span>{pct}%</span>" if label else ""
    return (f'<div class="pt-prog-row"><div class="pt-prog"><span style="width:{pct}%;background:{color}"></span></div>{lab}</div>')


def progress_color(pct: int, health: str) -> str:
    if health == "Terlambat":
        return HEALTH_COLORS["Terlambat"]
    if health == "Berisiko":
        return HEALTH_COLORS["Berisiko"]
    if pct >= 100:
        return HEALTH_COLORS["Aman"]
    return PRIMARY


def kpi(label: str, value, sub: str, color: str, ico: str) -> str:
    return (
        f'<div class="pt-kpi"><div class="pt-kpi-top"><span class="pt-label">{esc(label)}</span>'
        f'<span class="pt-kpi-ico" style="background:{tint(color)};color:{color}">{icon(ico, 16)}</span></div>'
        f'<div class="pt-kpi-val">{esc(value)}</div><div class="pt-kpi-sub">{sub}</div></div>'
    )


def due_text(row) -> str:
    if not has(row.get("due_date")):
        return "Tanpa tenggat"
    if row.get("status") == "Selesai":
        return f"Tenggat {fmt_date(row['due_date'])}"
    return f"{fmt_date(row['due_date'])} · {days_label(row.get('days_left'))}"


def project_card(row) -> str:
    gc = row.get("group_color") or FAINT
    health = row.get("health", "Aman")
    pct = int(row.get("progress_eff", 0) or 0)
    pin = f'<span style="color:{ACCENT}" title="Disematkan">{icon("pin", 13)}</span>' if has(row.get("pinned")) and int(row["pinned"]) else ""
    meta = [f'<span>{icon("calendar", 13)}{esc(due_text(row))}</span>']
    if row.get("tasks_total"):
        meta.append(f'<span>{icon("check", 13)}{int(row["tasks_done"])}/{int(row["tasks_total"])}</span>')
    if row.get("blockers_open"):
        meta.append(f'<span style="color:{HEALTH_COLORS["Terlambat"]}">{icon("alert", 13)}{int(row["blockers_open"])}</span>')
    if row.get("files_total"):
        meta.append(f'<span>{icon("clip", 13)}{int(row["files_total"])}</span>')
    nxt = ""
    if has(row.get("next_action")) and row.get("status") != "Selesai":
        nxt = f'<div class="pt-next">{icon("next", 14, PRIMARY)}<span>{esc(row["next_action"])}</span></div>'
    badges = [badge(row.get("priority", "Sedang"), PRIORITY_COLORS.get(row.get("priority"), MUTED), "flag")]
    if health != "Selesai":
        badges.append(badge(health, HEALTH_COLORS.get(health, MUTED)))
    return (
        f'<div class="pt-pcard-top">{group_chip(row.get("group_name", "Tanpa grup"), gc)}{pin}</div>'
        f'<div class="pt-pcard-title">{esc(row.get("name"))}</div>'
        f'<div class="pt-badges">{"".join(badges)}</div>'
        f'{progress_bar(pct, progress_color(pct, health))}'
        f'<div class="pt-meta">{"".join(meta)}</div>{nxt}'
    )


def list_row(title: str, sub: str, end: str, bar_color: str, href: str | None = None) -> str:
    tag_open = f'<a class="pt-row" href="{href}" target="_self">' if href else '<div class="pt-row">'
    tag_close = "</a>" if href else "</div>"
    return (
        f'{tag_open}<span class="pt-bar" style="background:{bar_color}"></span>'
        f'<div class="pt-row-main"><div class="pt-row-title">{esc(title)}</div><div class="pt-row-sub">{sub}</div></div>'
        f'<div class="pt-row-end">{end}</div>{tag_close}'
    )


def list_box(rows: list[str], empty: str = "Tidak ada data") -> str:
    if not rows:
        return f'<div class="pt-list"><div class="pt-row"><div class="pt-row-sub">{esc(empty)}</div></div></div>'
    return f'<div class="pt-list">{"".join(rows)}</div>'


def detail_href(pid: int) -> str:
    return f"./detail?id={int(pid)}"


# ---------------------------------------------------------------------------
# Grafik Plotly dengan gaya seragam
# ---------------------------------------------------------------------------
def style_fig(fig: go.Figure, height: int = 300, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12.5, color=INK),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(family=FONT, size=12.5, color=INK)),
    )
    fig.update_xaxes(gridcolor="#ECEAE4", zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor="#ECEAE4", zeroline=False, linecolor=LINE, tickfont=dict(color=INK))
    return fig


CHART_CONFIG = {"displayModeBar": False, "responsive": True}
