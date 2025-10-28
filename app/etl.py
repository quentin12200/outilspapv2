import pandas as pd, numpy as np, re
from dateutil.parser import parse as dtparse
from sqlalchemy.orm import Session
from datetime import datetime
from .models import PVEvent, Invitation, SiretSummary

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: re.sub(r"\s+", " ", str(c)).strip() for c in df.columns})
    df.columns = [c.lower() for c in df.columns]
    return df

def _to14(x):
    if pd.isna(x): return None
    s = re.sub(r"\D","", str(x))
    return s.zfill(14) if s else None

def _todate(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return None
    try:
        d = pd.to_datetime(x, dayfirst=True, errors="coerce")
        if pd.isna(d): 
            d = pd.to_datetime(dtparse(str(x), dayfirst=True))
        return d.date()
    except: 
        return None

def _col_detect(df, tokens):
    for t in tokens:
        if t in df.columns: return t
    for c in df.columns:
        for t in tokens:
            if t in c: return c
    return None

def _norm_cycle(x: str) -> str:
    s = str(x).upper()
    if "C3" in s or re.search(r"\b3\b", s): return "C3"
    if "C4" in s or re.search(r"\b4\b", s): return "C4"
    return s

# -------- Ingestion PV --------
def ingest_pv_excel(session: Session, file_like) -> int:
    xls = pd.ExcelFile(file_like)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df = _normalize_cols(df)

    c_siret   = _col_detect(df, ["siret"])
    c_cycle   = _col_detect(df, ["cycle"])
    # date PV: utiliser STRICTEMENT la colonne "date" si elle existe
    c_datepv = "date" if "date" in df.columns else (_col_detect(df, ["date pv","date pap","date_pv","date du pv","date du pap"]) or df.columns[min(15, len(df.columns)-1)])
    c_type    = _col_detect(df, ["type"])
    c_ins     = _col_detect(df, ["inscrit","inscrits"])
    c_vot     = _col_detect(df, ["votant","votants"])
    c_bn      = _col_detect(df, ["blanc","nul"])
    c_cgt     = [c for c in df.columns if "cgt" in c] or []
    c_idcc    = _col_detect(df, ["idcc"])
    c_fd      = _col_detect(df, ["fd"])
    c_ud      = _col_detect(df, ["ud"])
    c_dep     = _col_detect(df, ["départ","depart","département","departement","dep"])
    c_rs      = _col_detect(df, ["raison sociale","raison","dénomination","denomination","entreprise"])
    c_cp      = _col_detect(df, ["cp","code postal"])
    c_ville   = _col_detect(df, ["ville"])

    inserted = 0
    for _, r in df.iterrows():
        siret = _to14(r.get(c_siret))
        if not siret: 
            continue
        cycle = _norm_cycle(r.get(c_cycle))
        date_pv = _todate(r.get(c_datepv))
        type_ = str(r.get(c_type) or "")
        inscrits = _to_int(r.get(c_ins))
        votants = _to_int(r.get(c_vot))
        bn = _to_int(r.get(c_bn))
        cgt_voix = _sum_int([r.get(c) for c in c_cgt]) if c_cgt else None

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
            fd=(r.get(c_fd) if c_fd else None),
            ud=(r.get(c_ud) if c_ud else None),
            departement=(r.get(c_dep) if c_dep else None),
            raison_sociale=(r.get(c_rs) if c_rs else None),
            cp=(r.get(c_cp) if c_cp else None),
            ville=(r.get(c_ville) if c_ville else None),
        )
        session.add(ev)
        inserted += 1

    session.commit()
    return inserted

def _to_int(x):
    try:
        return int(float(str(x).replace(",", ".").strip()))
    except:
        return None

def _sum_int(vals):
    s = 0
    has = False
    for v in vals:
        try:
            s += int(float(str(v).replace(",", ".").strip()))
            has = True
        except:
            pass
    return s if has else None

# -------- Ingestion Invitations --------
def ingest_invit_excel(session: Session, file_like) -> int:
    xls = pd.ExcelFile(file_like)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df = _normalize_cols(df)

    c_siret = _col_detect(df, ["siret"])
    c_date  = _col_detect(df, ["date pap","date_pap","date","date invitation"])
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
            source="import_excel",
            raw=None
        )
        session.add(inv)
        inserted += 1
    session.commit()
    return inserted

# -------- Construire le résumé 1-ligne/SIRET --------
def build_siret_summary(session: Session) -> int:
    # Récup PV en pandas
    pvs = pd.read_sql(session.query(PVEvent).statement, session.bind)
    inv = pd.read_sql(session.query(Invitation).statement, session.bind)

    if pvs.empty:
        session.query(SiretSummary).delete()
        session.commit()
        return 0

    def pick_last(df_cycle):
        # garde la ligne la plus récente du cycle
        df_cycle = df_cycle.sort_values("date_pv", ascending=False)
        return df_cycle.head(1)

    # Normaliser
    pvs["carence"] = pvs["type"].fillna("").str.lower().str.contains("carence")
    # Filtrage bornes cycles
    C3_START, C3_END = pd.to_datetime("2017-01-01"), pd.to_datetime("2020-12-31")
    C4_START, C4_END = pd.to_datetime("2021-01-01"), pd.to_datetime("2024-12-31")
    C5_START, C5_END = pd.to_datetime("2025-01-01"), pd.to_datetime("2028-12-31")
    pvs["date_pv"] = pd.to_datetime(pvs["date_pv"], errors="coerce")
    mask_c3 = (pvs["cycle"]=="C3") & (pvs["date_pv"] >= C3_START) & (pvs["date_pv"] <= C3_END)
    mask_c4 = (pvs["cycle"]=="C4") & (pvs["date_pv"] >= C4_START) & (pvs["date_pv"] <= C4_END)
    last_c3 = (pvs[mask_c3].groupby("siret", as_index=False).apply(pick_last).reset_index(drop=True))
    last_c4 = (pvs[mask_c4].groupby("siret", as_index=False).apply(pick_last).reset_index(drop=True))

    # Invitations: dernière date par SIRET (filtrées C5)
    if not inv.empty:
        C5_START, C5_END = pd.to_datetime("2025-01-01"), pd.to_datetime("2028-12-31")
        inv["date_invit"] = pd.to_datetime(inv["date_invit"], errors="coerce")
        inv_c5 = inv[(inv["date_invit"] >= C5_START) & (inv["date_invit"] <= C5_END)]
        inv_latest = inv_c5.groupby("siret", as_index=False)["date_invit"].max().rename(columns={"date_invit":"date_pap_c5"})
    else:
        inv_latest = pd.DataFrame(columns=["siret","date_pap_c5"])

    # Fusion C3/C4
    base = last_c3.merge(last_c4, on="siret", how="outer", suffixes=("_c3","_c4"))

    # Colonnes consolidées
    base["raison_sociale"] = base["raison_sociale_c4"].fillna(base["raison_sociale_c3"])
    base["idcc"] = base["idcc_c4"].fillna(base["idcc_c3"])
    base["dep"] = base["departement_c4"].fillna(base["departement_c3"])
    base["cp"] = base["cp_c4"].fillna(base["cp_c3"])
    base["ville"] = base["ville_c4"].fillna(base["ville_c3"])

    base["statut_pap"] = np.where(base["date_pv_c3"].notna() & base["date_pv_c4"].notna(), "C3+C4",
                           np.where(base["date_pv_c4"].notna(), "C4",
                             np.where(base["date_pv_c3"].notna(), "C3", "Aucun")))
    # Correction : conversion explicite en datetime64
    base["date_pv_c3"] = pd.to_datetime(base["date_pv_c3"], errors="coerce")
    base["date_pv_c4"] = pd.to_datetime(base["date_pv_c4"], errors="coerce")
    base["date_pv_max"] = base[["date_pv_c3","date_pv_c4"]].max(axis=1)

    # Implantation CGT si voix > 0
    base["cgt_implantee"] = ((base["cgt_voix_c3"].fillna(0) > 0) | (base["cgt_voix_c4"].fillna(0) > 0))

    # Joindre invitations
    base = base.merge(inv_latest, on="siret", how="left")

    # Sélection finale / renommage
    outcols = dict(
        siret="siret",
        raison_sociale="raison_sociale",
        idcc="idcc",
        fd_c3="fd_c3",
        fd_c4="fd_c4",
        ud_c3="ud_c3",
        ud_c4="ud_c4",
        dep="dep", cp="cp", ville="ville",
        date_pv_c3="date_pv_c3", carence_c3="carence_c3", inscrits_c3="inscrits_c3",
        votants_c3="votants_c3", cgt_voix_c3="cgt_voix_c3",
        date_pv_c4="date_pv_c4", carence_c4="carence_c4", inscrits_c4="inscrits_c4",
        votants_c4="votants_c4", cgt_voix_c4="cgt_voix_c4",
        statut_pap="statut_pap", date_pv_max="date_pv_max", date_pap_c5="date_pap_c5",
        cgt_implantee="cgt_implantee"
    )

    # Construire DataFrame propre
    # Protection : ne jamais remplir les dates PV avec la date PAP
    safe_pv_c3 = base["date_pv_c3"]
    safe_pv_c4 = base["date_pv_c4"]
    safe_pv_max = base["date_pv_max"]
    if "date_pap_c5" in base:
        pap_dates = base["date_pap_c5"]
        # Exclure toute date de PV qui serait identique à une date PAP (même valeur)
        safe_pv_c3 = safe_pv_c3.where(~safe_pv_c3.isin(pap_dates.unique()), None)
        safe_pv_c4 = safe_pv_c4.where(~safe_pv_c4.isin(pap_dates.unique()), None)
        safe_pv_max = safe_pv_max.where(~safe_pv_max.isin(pap_dates.unique()), None)
    out = pd.DataFrame({
        "siret": base["siret"],
        "raison_sociale": base["raison_sociale"],
        "idcc": base["idcc"],
        "fd_c3": base.get("fd_c3"),
        "fd_c4": base.get("fd_c4"),
        "ud_c3": base.get("ud_c3"),
        "ud_c4": base.get("ud_c4"),
        "dep": base["dep"],
        "cp": base["cp"],
        "ville": base["ville"],
        "date_pv_c3": safe_pv_c3,
        "carence_c3": base.get("carence_c3"),
        "inscrits_c3": base.get("inscrits_c3"),
        "votants_c3": base.get("votants_c3"),
        "cgt_voix_c3": base.get("cgt_voix_c3"),
        "date_pv_c4": safe_pv_c4,
        "carence_c4": base.get("carence_c4"),
        "inscrits_c4": base.get("inscrits_c4"),
        "votants_c4": base.get("votants_c4"),
        "cgt_voix_c4": base.get("cgt_voix_c4"),
        "statut_pap": base["statut_pap"],
        "date_pv_max": safe_pv_max,
        "date_pap_c5": base.get("date_pap_c5"),
        "cgt_implantee": base["cgt_implantee"]
    })

    # Reset table (simple & robuste)
    session.query(SiretSummary).delete()
    session.commit()

    # Bulk-insert
    out = out.where(pd.notna(out), None)
    # Conversion ultime : tout NaN/NaT/None
    def nan_to_none(val):
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        return val
    rows = [{k: nan_to_none(v) for k, v in row.items()} for row in out.to_dict(orient="records")]
    session.bulk_insert_mappings(SiretSummary, rows)
    session.commit()
    return len(rows)
