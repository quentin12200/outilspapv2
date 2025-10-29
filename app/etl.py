import json
import logging
import pandas as pd
import numpy as np
import re
from collections import defaultdict
from datetime import date
from dateutil.parser import parse as dtparse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .models import PVEvent, Invitation, SiretSummary
from .normalization import normalize_fd_label, normalize_os_label, format_os_scores

logger = logging.getLogger(__name__)


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: re.sub(r"\s+", " ", str(c)).strip() for c in df.columns})
    df.columns = [c.lower() for c in df.columns]
    return df


def _to14(x):
    if pd.isna(x):
        return None
    s = re.sub(r"\D", "", str(x))
    return s.zfill(14) if s else None


def _todate(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    try:
        d = pd.to_datetime(x, dayfirst=True, errors="coerce")
        if pd.isna(d):
            d = pd.to_datetime(dtparse(str(x), dayfirst=True))
        return d.date()
    except Exception:
        return None


def _col_detect(df, tokens):
    for t in tokens:
        if t in df.columns:
            return t
    for c in df.columns:
        for t in tokens:
            if t in c:
                return c
    return None


def _norm_cycle(x: str) -> str:
    s = str(x or "").upper()
    if "C3" in s or re.search(r"\b3\b", s):
        return "C3"
    if "C4" in s or re.search(r"\b4\b", s):
        return "C4"
    return s or None


def _to_int(x):
    try:
        return int(float(str(x).replace(",", ".").strip()))
    except Exception:
        return None


def _sum_int(vals):
    s = 0
    has = False
    for v in vals:
        try:
            s += int(float(str(v).replace(",", ".").strip()))
            has = True
        except Exception:
            pass
    return s if has else None


# -------- Schema helpers --------
def ensure_schema(engine) -> None:
    """Ensure optional columns exist after historic deployments."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "invitations" in existing_tables:
        cols = {col["name"] for col in inspector.get_columns("invitations")}
        alters = []
        if "raison_sociale" not in cols:
            alters.append("ALTER TABLE invitations ADD COLUMN raison_sociale TEXT")
        if "departement" not in cols:
            alters.append("ALTER TABLE invitations ADD COLUMN departement VARCHAR(5)")
        if "fd" not in cols:
            alters.append("ALTER TABLE invitations ADD COLUMN fd VARCHAR(80)")
        if alters:
            with engine.begin() as conn:
                for stmt in alters:
                    conn.execute(text(stmt))

    if "pv_events" in existing_tables:
        cols = {col["name"] for col in inspector.get_columns("pv_events")}
        if "autres_indics" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE pv_events ADD COLUMN autres_indics JSON")
                )


# -------- Ingestion PV --------
def _row_payload(row: pd.Series) -> dict:
    payload: dict[str, str] = {}
    for key, value in row.items():
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        text_value = str(value).strip()
        if not text_value:
            continue
        payload[str(key)] = text_value
    return payload


def ingest_pv_excel(session: Session, file_like) -> int:
    xls = pd.ExcelFile(file_like)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df = _normalize_cols(df)

    c_siret = _col_detect(df, ["siret"])
    c_cycle = _col_detect(df, ["cycle"])
    c_datepv = "date" if "date" in df.columns else (
        _col_detect(df, ["date pv", "date pap", "date_pv", "date du pv", "date du pap"]) or df.columns[min(15, len(df.columns) - 1)]
    )
    c_type = _col_detect(df, ["type"])
    c_ins = _col_detect(df, ["inscrit", "inscrits"])
    c_vot = _col_detect(df, ["votant", "votants"])
    c_bn = _col_detect(df, ["blanc", "nul"])
    c_cgt = [c for c in df.columns if "cgt" in c] or []
    c_idcc = _col_detect(df, ["idcc"])
    c_fd = _col_detect(df, ["fd"])
    c_ud = _col_detect(df, ["ud"])
    c_dep = _col_detect(df, ["départ", "depart", "département", "departement", "dep"])
    c_rs = _col_detect(df, ["raison sociale", "raison", "dénomination", "denomination", "entreprise"])
    c_cp = _col_detect(df, ["cp", "code postal"])
    c_ville = _col_detect(df, ["ville"])

    inserted = 0
    for _, r in df.iterrows():
        siret = _to14(r.get(c_siret))
        if not siret:
            continue
        cycle = _norm_cycle(r.get(c_cycle))
        if cycle not in {"C3", "C4"}:
            continue
        date_pv = _todate(r.get(c_datepv))
        type_ = str(r.get(c_type) or "")
        inscrits = _to_int(r.get(c_ins))
        votants = _to_int(r.get(c_vot))
        bn = _to_int(r.get(c_bn))
        cgt_voix = _sum_int([r.get(c) for c in c_cgt]) if c_cgt else None

        autres = _row_payload(r)

        ev = PVEvent(
            siret=siret,
            cycle=cycle,
            date_pv=date_pv,
            type=type_,
            inscrits=inscrits,
            votants=votants,
            blancs_nuls=bn,
            cgt_voix=cgt_voix,
            idcc=(r.get(c_idcc) if c_idcc else None),
            fd=normalize_fd_label(r.get(c_fd) if c_fd else None),
            ud=(r.get(c_ud) if c_ud else None),
            departement=(r.get(c_dep) if c_dep else None),
            raison_sociale=(r.get(c_rs) if c_rs else None),
            cp=(r.get(c_cp) if c_cp else None),
            ville=(r.get(c_ville) if c_ville else None),
            autres_indics=autres or None,
        )
        session.add(ev)
        inserted += 1

    session.commit()
    return inserted


# -------- Ingestion Invitations --------
def ingest_invit_excel(session: Session, file_like) -> int:
    xls = pd.ExcelFile(file_like)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df = _normalize_cols(df)

    c_siret = _col_detect(df, ["siret"])
    c_date = _col_detect(df, ["date pap", "date_pap", "date", "date invitation"])
    c_rs = _col_detect(df, ["raison sociale", "raison", "dénomination", "denomination", "entreprise"])
    c_dep = _col_detect(df, ["départ", "depart", "département", "departement", "dep"])
    c_fd = _col_detect(df, ["fd", "fédération", "federation"])

    inserted = 0
    for _, r in df.iterrows():
        siret = _to14(r.get(c_siret))
        if not siret:
            continue
        date_invit = _todate(r.get(c_date))
        if not date_invit:
            continue
        inv = Invitation(
            siret=siret,
            date_invit=date_invit,
            raison_sociale=r.get(c_rs) if c_rs else None,
            departement=r.get(c_dep) if c_dep else None,
            fd=normalize_fd_label(r.get(c_fd) if c_fd else None),
            source="import_excel",
            raw=None,
        )
        session.add(inv)
        inserted += 1
    session.commit()
    return inserted


# -------- Helpers for aggregation --------
def _ensure_summary_table(session: Session) -> None:
    """Drop & recreate the derived summary table to match the ORM schema."""
    SiretSummary.__table__.drop(bind=session.bind, checkfirst=True)
    SiretSummary.__table__.create(bind=session.bind, checkfirst=True)


def _safe_date(value) -> date | None:
    if isinstance(value, date):
        return value
    return None


def _extract_os_scores(payload) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)

    def add(label, raw_value) -> None:
        canonical = normalize_os_label(label)
        if not canonical:
            return
        try:
            numeric = float(str(raw_value).replace("%", "").replace(",", "."))
        except Exception:
            return
        scores[canonical] += numeric

    def walk(value) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for key, sub in value.items():
                if isinstance(sub, (dict, list)):
                    walk(sub)
                else:
                    add(key, sub)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return
            try:
                parsed = json.loads(stripped)
            except Exception:
                for token in re.split(r"[;\n]+", stripped):
                    token = token.strip()
                    if not token:
                        continue
                    match = re.match(r"(.+?)[=:]\\s*([-+]?[0-9]+(?:[\.,][0-9]+)?)", token)
                    if match:
                        add(match.group(1), match.group(2))
            else:
                walk(parsed)
        else:
            try:
                key, val = value
            except Exception:
                return
            add(key, val)

    walk(payload)
    return {k: round(v, 4) for k, v in scores.items()}


# -------- Construire le résumé 1-ligne/SIRET --------
def build_siret_summary(session: Session) -> int:
    pv_rows = session.query(
        PVEvent.siret,
        PVEvent.cycle,
        PVEvent.date_pv,
        PVEvent.autres_indics,
        PVEvent.fd,
        PVEvent.departement,
        PVEvent.raison_sociale,
    ).filter(PVEvent.cycle.in_(["C3", "C4"]))

    inv_rows = session.query(
        Invitation.siret,
        Invitation.date_invit,
        Invitation.raison_sociale,
        Invitation.departement,
        Invitation.fd,
    )

    pv_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"C3": 0, "C4": 0})
    latest_c3: dict[str, dict] = {}
    latest_c4: dict[str, dict] = {}

    for siret, cycle, date_pv, autres, fd, dep, rs in pv_rows:
        if not siret or cycle not in {"C3", "C4"}:
            continue
        pv_counts[siret][cycle] += 1
        target = latest_c3 if cycle == "C3" else latest_c4
        stored = target.get(siret)
        current_date = _safe_date(date_pv) or date.min
        stored_date = _safe_date(stored["date_pv"]) if stored else date.min
        if stored is None or current_date >= stored_date:
            target[siret] = {
                "date_pv": _safe_date(date_pv),
                "fd": normalize_fd_label(fd),
                "departement": dep,
                "raison_sociale": rs,
                "scores": _extract_os_scores(autres),
            }

    invit_counts: dict[str, int] = defaultdict(int)
    invit_latest: dict[str, dict] = {}

    for siret, date_invit, rs, dep, fd in inv_rows:
        if not siret:
            continue
        invit_counts[siret] += 1
        stored = invit_latest.get(siret)
        current_date = _safe_date(date_invit) or date.min
        stored_date = _safe_date(stored["date_pap_c5"]) if stored else date.min
        if stored is None or current_date >= stored_date:
            invit_latest[siret] = {
                "date_pap_c5": _safe_date(date_invit),
                "raison_sociale": rs,
                "departement": dep,
                "fd": normalize_fd_label(fd),
            }

    if not pv_counts and not invit_counts:
        _ensure_summary_table(session)
        return 0

    all_sirets = set(pv_counts.keys()) | set(invit_counts.keys()) | set(latest_c3.keys()) | set(latest_c4.keys())

    rows = []
    for siret in sorted(all_sirets):
        inv_info = invit_latest.get(siret, {})
        c3_info = latest_c3.get(siret)
        c4_info = latest_c4.get(siret)

        counts = pv_counts.get(siret, {"C3": 0, "C4": 0})
        has_c3 = bool(c3_info and counts.get("C3", 0))
        has_c4 = bool(c4_info and counts.get("C4", 0))
        presence = "Aucune"
        if has_c3 and has_c4:
            presence = "C3+C4"
        elif has_c3:
            presence = "C3"
        elif has_c4:
            presence = "C4"

        fd_value = c4_info.get("fd") if c4_info else None
        if not fd_value and c3_info:
            fd_value = c3_info.get("fd")
        if not fd_value:
            fd_value = inv_info.get("fd")

        departement = c4_info.get("departement") if c4_info else None
        if not departement and c3_info:
            departement = c3_info.get("departement")
        if not departement:
            departement = inv_info.get("departement")

        raison_sociale = c4_info.get("raison_sociale") if c4_info else None
        if not raison_sociale and c3_info:
            raison_sociale = c3_info.get("raison_sociale")
        if not raison_sociale:
            raison_sociale = inv_info.get("raison_sociale")

        date_pv_c3 = c3_info.get("date_pv") if c3_info else None
        date_pv_c4 = c4_info.get("date_pv") if c4_info else None
        pv_dates = [d for d in [date_pv_c3, date_pv_c4] if d]
        date_pv_last = max(pv_dates) if pv_dates else None

        os_c3 = format_os_scores(c3_info.get("scores", {})) if c3_info else ""
        os_c4 = format_os_scores(c4_info.get("scores", {})) if c4_info else ""

        date_pap_c5 = inv_info.get("date_pap_c5")
        has_match = bool(date_pap_c5 and (has_c3 or has_c4))

        rows.append(
            {
                "siret": siret,
                "raison_sociale": raison_sociale,
                "departement": departement,
                "fd": fd_value,
                "has_c3": has_c3,
                "has_c4": has_c4,
                "presence": presence,
                "os_c3": os_c3 or None,
                "os_c4": os_c4 or None,
                "date_pv_c3": date_pv_c3,
                "date_pv_c4": date_pv_c4,
                "date_pv_last": date_pv_last,
                "date_pap_c5": date_pap_c5,
                "invitation_count": invit_counts.get(siret, 0) or None,
                "pv_c3_count": counts.get("C3", 0) or None,
                "pv_c4_count": counts.get("C4", 0) or None,
                "has_match_c5_pv": has_match,
            }
        )

    _ensure_summary_table(session)
    if not rows:
        session.commit()
        return 0

    session.bulk_insert_mappings(SiretSummary, rows)
    session.commit()
    return len(rows)


# -------- Global statistics --------
def compute_global_stats(session: Session) -> dict:
    from sqlalchemy import select, func, union_all

    pap_c5_rows = session.execute(select(func.count(Invitation.id))).scalar_one() or 0
    pap_c5_sirets = session.execute(select(func.count(func.distinct(Invitation.siret)))).scalar_one() or 0

    pv_c3_rows = session.execute(
        select(func.count()).select_from(PVEvent).where(PVEvent.cycle == "C3")
    ).scalar_one() or 0
    pv_c4_rows = session.execute(
        select(func.count()).select_from(PVEvent).where(PVEvent.cycle == "C4")
    ).scalar_one() or 0

    pv_c3_sirets = session.execute(select(func.count(func.distinct(PVEvent.siret))).where(PVEvent.cycle == "C3")).scalar_one() or 0
    pv_c4_sirets = session.execute(select(func.count(func.distinct(PVEvent.siret))).where(PVEvent.cycle == "C4")).scalar_one() or 0

    inv_sirets = select(Invitation.siret.label("siret")).where(Invitation.siret.isnot(None))
    pv_c3_sirets_q = select(PVEvent.siret.label("siret")).where(PVEvent.cycle == "C3", PVEvent.siret.isnot(None))
    pv_c4_sirets_q = select(PVEvent.siret.label("siret")).where(PVEvent.cycle == "C4", PVEvent.siret.isnot(None))

    union_sirets = union_all(inv_sirets, pv_c3_sirets_q, pv_c4_sirets_q).subquery()
    structures_distinct = session.execute(
        select(func.count(func.distinct(union_sirets.c.siret)))
    ).scalar_one() or 0

    inv_distinct_sub = select(Invitation.siret.label("siret")).where(Invitation.siret.isnot(None)).distinct().subquery()
    pv_c3_distinct_sub = select(PVEvent.siret.label("siret")).where(PVEvent.cycle == "C3", PVEvent.siret.isnot(None)).distinct().subquery()
    pv_c4_distinct_sub = select(PVEvent.siret.label("siret")).where(PVEvent.cycle == "C4", PVEvent.siret.isnot(None)).distinct().subquery()

    match_c5_c3_sirets = session.execute(
        select(func.count()).select_from(
            inv_distinct_sub.join(pv_c3_distinct_sub, inv_distinct_sub.c.siret == pv_c3_distinct_sub.c.siret)
        )
    ).scalar_one() or 0

    match_c5_c4_sirets = session.execute(
        select(func.count()).select_from(
            inv_distinct_sub.join(pv_c4_distinct_sub, inv_distinct_sub.c.siret == pv_c4_distinct_sub.c.siret)
        )
    ).scalar_one() or 0

    return {
        "structures_distinct": structures_distinct,
        "pap_c5_rows": pap_c5_rows,
        "pap_c5_sirets": pap_c5_sirets,
        "pv_c3_rows": pv_c3_rows,
        "pv_c3_sirets": pv_c3_sirets,
        "pv_c4_rows": pv_c4_rows,
        "pv_c4_sirets": pv_c4_sirets,
        "match_c5_c3_sirets": match_c5_c3_sirets,
        "match_c5_c4_sirets": match_c5_c4_sirets,
    }
