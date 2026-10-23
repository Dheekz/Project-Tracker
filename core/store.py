"""Backend penyimpanan: Google Sheets (utama) atau SQLite (cadangan lokal).

Setiap tabel = satu tab di Google Sheet, baris pertama = nama kolom.
Lapisan di atasnya (core/db.py) hanya memakai 6 operasi:
    read_all, insert, update_many, delete_many, replace_all, info
"""
from __future__ import annotations

import math
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from core.schema import CHOICES, DEFAULTS, REQUIRED, TABLE_ORDER, TABLES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SQLITE = os.path.join(BASE_DIR, "data", "tracker.db")
SHEET_EPOCH = datetime(1899, 12, 30)


class StoreConfigError(RuntimeError):
    """Konfigurasi backend belum lengkap atau salah."""


# ---------------------------------------------------------------------------
# Normalisasi nilai (berlaku untuk input dari Sheet maupun SQLite)
# ---------------------------------------------------------------------------
def _blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and v.strip() == ""


def _to_int(v, default=0):
    if isinstance(v, bool):
        return int(v)
    if _blank(v):
        return default
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "ya", "yes", "y", "x", "v", "selesai"):
            return 1
        if s in ("false", "tidak", "no", "n"):
            return 0
        s = s.replace(",", ".")
        try:
            return int(float(s))
        except ValueError:
            return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _to_date(v) -> str | None:
    if _blank(v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (SHEET_EPOCH + timedelta(days=float(v))).date().isoformat()
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    try:
        return pd.to_datetime(s, dayfirst=True).date().isoformat()
    except (ValueError, TypeError):
        return None


def _to_ts(v) -> str | None:
    if _blank(v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (SHEET_EPOCH + timedelta(days=float(v))).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _to_text(v) -> str:
    if _blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _choice(v: str, options: list[str], default: str) -> str:
    if v in options:
        return v
    low = {o.lower(): o for o in options}
    return low.get(v.lower().strip(), default) if v else default


def normalize_value(table: str, col: str, v):
    kind = TABLES[table][col]
    if kind == "int":
        return _to_int(v, 0)
    if kind == "intn":
        return None if _blank(v) else _to_int(v, None)
    if kind == "date":
        return _to_date(v)
    if kind == "ts":
        return _to_ts(v)
    text = _to_text(v)
    if (table, col) in CHOICES:
        opts, default = CHOICES[(table, col)]
        return _choice(text, opts, default)
    if not text and col in DEFAULTS:
        return DEFAULTS[col]
    return text


def normalize_df(table: str, raw: pd.DataFrame) -> pd.DataFrame:
    cols = list(TABLES[table])
    df = raw.copy() if raw is not None else pd.DataFrame()
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    req = REQUIRED.get(table)
    if req and len(df):
        df = df[~df[req].map(_blank)]
    df = df[~df["id"].map(_blank)] if len(df) else df
    rows = [{c: normalize_value(table, c, r[c]) for c in cols} for r in df.to_dict("records")]
    out = pd.DataFrame(rows, columns=cols)
    for c, kind in TABLES[table].items():
        if kind == "int":
            out[c] = out[c].astype("int64") if len(out) else pd.Series(dtype="int64")
        elif kind == "intn":
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
        else:
            out[c] = out[c].astype(object)
    out = out.drop_duplicates(subset="id", keep="first")
    return out.reset_index(drop=True)


def to_cell(v):
    """Nilai Python ke sel Sheet. None/NaN jadi string kosong."""
    if _blank(v):
        return ""
    if isinstance(v, bool):
        return int(v)
    if hasattr(v, "item"):  # numpy scalar
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _record(table: str, rec: dict) -> dict:
    return {c: normalize_value(table, c, rec.get(c)) for c in TABLES[table]}


# ---------------------------------------------------------------------------
# Backend Google Sheets
# ---------------------------------------------------------------------------
class SheetsStore:
    kind = "gsheets"

    def __init__(self, spreadsheet):
        self.sh = spreadsheet
        self._sheets: dict[str, Any] = {}

    # -- utilitas ----------------------------------------------------------
    @staticmethod
    def _rng(table: str, a1: str = "") -> str:
        return f"'{table}'!{a1}" if a1 else f"'{table}'"

    @staticmethod
    def _a1(row: int, col: int) -> str:
        letters = ""
        while col:
            col, rem = divmod(col - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{row}"

    def info(self) -> dict:
        return {"backend": "Google Sheets", "url": getattr(self.sh, "url", ""), "title": getattr(self.sh, "title", "")}

    def ensure_schema(self) -> None:
        """Buat tab yang belum ada, lengkapi header, pasang dropdown dan header beku."""
        existing = {ws.title: ws for ws in self.sh.worksheets()}
        present = [t for t in TABLES if t in existing]
        heads = self.sh.values_batch_get([self._rng(t, "1:1") for t in present]) if present else {}
        head_map = {}
        for t, vr in zip(present, heads.get("valueRanges", [])):
            vals = vr.get("values", [])
            head_map[t] = [str(h).strip() for h in vals[0]] if vals else []

        header_writes = []
        for t, cols in TABLES.items():
            if t not in existing:
                ws = self.sh.add_worksheet(title=t, rows=200, cols=len(cols) + 2)
                existing[t] = ws
                head_map[t] = []
            ws = existing[t]
            header = [h for h in head_map[t] if h]
            missing = [c for c in cols if c not in header]
            if missing:
                new_header = header + missing
                if getattr(ws, "col_count", len(new_header)) < len(new_header):
                    ws.add_cols(len(new_header) - ws.col_count)
                header_writes.append({"range": self._rng(t, "A1"), "values": [new_header]})
                head_map[t] = new_header
            self._sheets[t] = ws
        if header_writes:
            self.sh.values_batch_update({"valueInputOption": "RAW", "data": header_writes})

        # Format: header beku + tebal, dropdown untuk kolom pilihan
        requests = []
        for t, ws in self._sheets.items():
            sid = ws.id
            requests.append({"updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount"}})
            requests.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                               "backgroundColor": {"red": 0.93, "green": 0.95, "blue": 0.94}}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
            header = head_map[t]
            for (tt, col), (opts, _d) in CHOICES.items():
                if tt != t or col not in header:
                    continue
                ci = header.index(col)
                requests.append({"setDataValidation": {
                    "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 5000,
                              "startColumnIndex": ci, "endColumnIndex": ci + 1},
                    "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in opts]},
                             "showCustomUi": True, "strict": False}}})
        if requests:
            self.sh.batch_update({"requests": requests})

    def _ws(self, table: str):
        if table not in self._sheets:
            self._sheets = {ws.title: ws for ws in self.sh.worksheets()}
        return self._sheets[table]

    @staticmethod
    def _grid(vr: dict) -> tuple[list[str], list[list]]:
        values = vr.get("values", []) or []
        if not values:
            return [], []
        header = [str(h).strip() for h in values[0]]
        rows = [list(r) + [""] * (len(header) - len(r)) for r in values[1:]]
        return header, [r[:len(header)] for r in rows]

    def _fresh(self, tables: list[str]) -> dict[str, tuple[list[str], list[list]]]:
        resp = self.sh.values_batch_get([self._rng(t) for t in tables],
                                        params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return {t: self._grid(vr) for t, vr in zip(tables, resp.get("valueRanges", []))}

    # -- baca --------------------------------------------------------------
    def read_all(self) -> dict[str, pd.DataFrame]:
        grids = self._fresh(TABLE_ORDER)
        fixes = []
        out = {}
        for t, (header, rows) in grids.items():
            df = pd.DataFrame(rows, columns=header) if header else pd.DataFrame(columns=list(TABLES[t]))
            if "id" in df.columns and len(df):
                # Baris yang ditambah manual di Sheet tanpa id: beri id otomatis
                ids = pd.to_numeric(df["id"].map(lambda v: _to_int(v, None)), errors="coerce")
                filled = df.drop(columns=["id"]).apply(lambda r: any(not _blank(x) for x in r), axis=1)
                need = ids.isna() & filled
                if need.any():
                    nxt = int(ids.max()) + 1 if ids.notna().any() else 1
                    ci = header.index("id") + 1
                    for idx in df.index[need]:
                        df.at[idx, "id"] = nxt
                        fixes.append({"range": self._rng(t, self._a1(idx + 2, ci)), "values": [[nxt]]})
                        nxt += 1
            out[t] = normalize_df(t, df)
        if fixes:
            self.sh.values_batch_update({"valueInputOption": "RAW", "data": fixes})
        return out

    # -- tulis -------------------------------------------------------------
    def insert(self, table: str, records: list[dict]) -> list[int]:
        if not records:
            return []
        header, rows = self._fresh([table])[table]
        header = header or list(TABLES[table])
        ci = header.index("id")
        ids = [_to_int(r[ci], 0) for r in rows]
        nxt = max(ids + [0]) + 1
        new_ids, values = [], []
        for rec in records:
            rec = _record(table, rec)
            rec["id"] = nxt
            new_ids.append(nxt)
            nxt += 1
            values.append([to_cell(rec.get(h)) if h in TABLES[table] else "" for h in header])
        self.sh.values_append(self._rng(table, "A1"),
                              params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                              body={"values": values})
        return new_ids

    def update_many(self, table: str, updates: dict[int, dict]) -> None:
        if not updates:
            return
        header, rows = self._fresh([table])[table]
        ci = header.index("id")
        pos = {_to_int(r[ci], None): i + 2 for i, r in enumerate(rows)}
        data = []
        for rid, fields in updates.items():
            row = pos.get(int(rid))
            if row is None:
                continue
            for col, val in fields.items():
                if col not in header or col not in TABLES[table]:
                    continue
                cell = to_cell(normalize_value(table, col, val))
                data.append({"range": self._rng(table, self._a1(row, header.index(col) + 1)), "values": [[cell]]})
        if data:
            self.sh.values_batch_update({"valueInputOption": "RAW", "data": data})

    def delete_many(self, spec: dict[str, list[int]]) -> None:
        spec = {t: [int(i) for i in ids] for t, ids in spec.items() if ids}
        if not spec:
            return
        grids = self._fresh(list(spec))
        requests = []
        for t, ids in spec.items():
            header, rows = grids[t]
            ci = header.index("id")
            wanted = set(ids)
            idxs = sorted((i + 1 for i, r in enumerate(rows) if _to_int(r[ci], None) in wanted), reverse=True)
            sid = self._ws(t).id
            for i in idxs:
                requests.append({"deleteDimension": {
                    "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}}})
        if requests:
            self.sh.batch_update({"requests": requests})

    def replace_all(self, table: str, records: list[dict]) -> None:
        self.replace_many({table: records})

    def replace_many(self, data: dict[str, list[dict]]) -> None:
        """Ganti isi beberapa tab sekaligus: 1 clear + 1 tulis header + 1 append per tab berisi."""
        tables = list(data)
        self.sh.values_batch_clear(body={"ranges": [self._rng(t) for t in tables]})
        self.sh.values_batch_update({"valueInputOption": "RAW", "data": [
            {"range": self._rng(t, "A1"), "values": [list(TABLES[t])]} for t in tables]})
        for t in tables:
            if data[t]:
                header = list(TABLES[t])
                values = [[to_cell(_record(t, r).get(h)) for h in header] for r in data[t]]
                self.sh.values_append(self._rng(t, "A1"),
                                      params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                                      body={"values": values})


# ---------------------------------------------------------------------------
# Backend SQLite (dipakai bila Google Sheet belum dikonfigurasi)
# ---------------------------------------------------------------------------
class SqliteStore:
    kind = "sqlite"

    def __init__(self, path: str):
        self.path = path

    def info(self) -> dict:
        return {"backend": "SQLite lokal", "url": "", "title": self.path}

    def _conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        conn = self._conn()
        try:
            with conn:
                for t, cols in TABLES.items():
                    defs = ", ".join(
                        f"{c} INTEGER PRIMARY KEY" if c == "id" else f"{c} {'INTEGER' if k == 'int' else 'TEXT'}"
                        for c, k in cols.items()
                    )
                    conn.execute(f"CREATE TABLE IF NOT EXISTS {t} ({defs})")
                    have = {r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()}
                    for c, k in cols.items():
                        if c not in have:
                            conn.execute(f"ALTER TABLE {t} ADD COLUMN {c} {'INTEGER' if k == 'int' else 'TEXT'}")
                    conn.execute(f"UPDATE {t} SET id = rowid WHERE id IS NULL")
        finally:
            conn.close()

    def read_all(self) -> dict[str, pd.DataFrame]:
        conn = self._conn()
        try:
            return {t: normalize_df(t, pd.read_sql_query(f"SELECT * FROM {t}", conn)) for t in TABLES}
        finally:
            conn.close()

    def insert(self, table: str, records: list[dict]) -> list[int]:
        if not records:
            return []
        cols = list(TABLES[table])
        conn = self._conn()
        try:
            with conn:
                nxt = (conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0] or 0) + 1
                ids = []
                for rec in records:
                    rec = _record(table, rec)
                    rec["id"] = nxt
                    conn.execute(f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)})",
                                 [to_cell(rec[c]) if not _blank(rec[c]) else None for c in cols])
                    ids.append(nxt)
                    nxt += 1
                return ids
        finally:
            conn.close()

    def update_many(self, table: str, updates: dict[int, dict]) -> None:
        conn = self._conn()
        try:
            with conn:
                for rid, fields in updates.items():
                    fields = {c: normalize_value(table, c, v) for c, v in fields.items() if c in TABLES[table] and c != "id"}
                    if not fields:
                        continue
                    sets = ", ".join(f"{c}=?" for c in fields)
                    conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*fields.values(), int(rid)])
        finally:
            conn.close()

    def delete_many(self, spec: dict[str, list[int]]) -> None:
        conn = self._conn()
        try:
            with conn:
                for t, ids in spec.items():
                    if ids:
                        conn.execute(f"DELETE FROM {t} WHERE id IN ({', '.join('?' for _ in ids)})", [int(i) for i in ids])
        finally:
            conn.close()

    def replace_many(self, data: dict[str, list[dict]]) -> None:
        for t, records in data.items():
            self.replace_all(t, records)

    def replace_all(self, table: str, records: list[dict]) -> None:
        cols = list(TABLES[table])
        conn = self._conn()
        try:
            with conn:
                conn.execute(f"DELETE FROM {table}")
                for rec in records:
                    rec = _record(table, rec)
                    conn.execute(f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)})",
                                 [None if _blank(rec[c]) else to_cell(rec[c]) for c in cols])
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Pemilihan backend dan cache baca
# ---------------------------------------------------------------------------
_OVERRIDE = None  # dipakai untuk pengujian


def set_override(store) -> None:
    global _OVERRIDE
    _OVERRIDE = store
    get_store.clear()
    read_cached.clear()


def _secrets_section(name: str) -> dict:
    try:
        return dict(st.secrets.get(name, {}))
    except Exception:  # noqa: BLE001  (tidak ada secrets.toml)
        return {}


def config() -> dict:
    tracker = _secrets_section("tracker")
    backend = os.environ.get("TRACKER_BACKEND") or tracker.get("backend")
    spreadsheet = os.environ.get("TRACKER_SPREADSHEET") or tracker.get("spreadsheet", "")
    if not backend:
        backend = "gsheets" if spreadsheet else "sqlite"
    return {
        "backend": backend,
        "spreadsheet": spreadsheet,
        "cache_ttl": int(os.environ.get("TRACKER_CACHE_TTL") or tracker.get("cache_ttl", 30)),
        "sqlite_path": os.environ.get("TRACKER_DB_PATH") or tracker.get("sqlite_path", DEFAULT_SQLITE),
        "credentials_file": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
    }


def _open_spreadsheet(cfg: dict):
    try:
        import gspread
    except ImportError as exc:
        raise StoreConfigError("Paket gspread belum terpasang. Jalankan: pip install -r requirements.txt") from exc
    sa = _secrets_section("gcp_service_account")
    if sa:
        client = gspread.service_account_from_dict(sa)
    elif cfg["credentials_file"]:
        client = gspread.service_account(filename=cfg["credentials_file"])
    else:
        raise StoreConfigError(
            "Kredensial service account belum ada. Isi bagian [gcp_service_account] di .streamlit/secrets.toml."
        )
    target = cfg["spreadsheet"].strip()
    if not target:
        raise StoreConfigError("Alamat Google Sheet belum diisi di [tracker] spreadsheet pada secrets.toml.")
    try:
        return client.open_by_url(target) if target.startswith("http") else client.open_by_key(target)
    except gspread.exceptions.SpreadsheetNotFound as exc:
        email = sa.get("client_email", "email service account")
        raise StoreConfigError(
            f"Google Sheet tidak ditemukan atau belum dibagikan. Bagikan Sheet ke {email} sebagai Editor."
        ) from exc
    except gspread.exceptions.APIError as exc:
        raise StoreConfigError(f"Google API menolak akses: {exc}. Pastikan Google Sheets API sudah diaktifkan.") from exc


@st.cache_resource(show_spinner="Menyiapkan penyimpanan...")
def get_store():
    if _OVERRIDE is not None:
        _OVERRIDE.ensure_schema()
        return _OVERRIDE
    cfg = config()
    if cfg["backend"] == "gsheets":
        store = SheetsStore(_open_spreadsheet(cfg))
    else:
        store = SqliteStore(cfg["sqlite_path"])
    store.ensure_schema()
    return store


@st.cache_data(show_spinner=False, ttl=int(config().get("cache_ttl", 30)))
def read_cached() -> dict[str, pd.DataFrame]:
    return get_store().read_all()


def invalidate() -> None:
    read_cached.clear()
