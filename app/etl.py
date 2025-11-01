import pandas as pd, numpy as np, re, unicodedata
from dateutil.parser import parse as dtparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime
from .models import PVEvent, Invitation, SiretSummary

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: re.sub(r"\s+", " ", str(c)).strip() for c in df.columns})
    df.columns = [c.lower() for c in df.columns]
    return df

def _normalize_raw_key(key: str) -> str:
    key = unicodedata.normalize("NFKD", str(key))
    key = "".join(ch for ch in key if not unicodedata.combining(ch))
    key = key.lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")

def _clean_raw_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"nan", "none", "null"}:
            return None
        return cleaned
    return value

def _build_raw_payload(row: pd.Series) -> dict[str, str]:
    payload: dict[str, str] = {}
    for col, value in row.items():
        cleaned = _clean_raw_value(value)
        if cleaned is None:
            continue
        key = _normalize_raw_key(col)
        if not key:
            continue
        if key not in payload:
            payload[key] = cleaned
    return payload

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
        inscrits = _to_int(r.get(c_ins))
        votants = _to_int(r.get(c_vot))
        cgt_voix = _sum_int([r.get(c) for c in c_cgt]) if c_cgt else None

        ev = PVEvent(
            siret=siret,
            cycle=cycle,
            date_pv=date_pv,
            inscrits=inscrits,
            votants=votants,
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
        raw_payload = _build_raw_payload(r)

        def pick(*keys: str) -> str | None:
            for key in keys:
                norm = _normalize_raw_key(key)
                if norm and norm in raw_payload:
                    return raw_payload[norm]
            return None

        def pick_bool(*keys: str):
            value = pick(*keys)
            if value is None:
                return None
            lowered = str(value).strip().lower()
            if lowered in {"1", "oui", "o", "yes", "y", "true"}:
                return True
            if lowered in {"0", "non", "n", "no", "false"}:
                return False
            return None

        def pick_first_truthy(*keys: str) -> str | None:
            for key in keys:
                value = pick(key)
                if value:
                    return value
            return None

        inv = Invitation(
            siret=siret,
            date_invit=date_invit,
            source=pick_first_truthy("source", "origine", "canal") or "import_excel",
            raw=raw_payload or None,
            denomination=pick_first_truthy(
                "denomination", "denomination_usuelle", "raison_sociale", "raison sociale",
                "raison_sociale_etablissement", "nom_raison_sociale", "rs", "nom",
                "nom_entreprise", "societe", "entreprise", "nom_de_l_entreprise", "libelle"
            ),
            enseigne=pick_first_truthy("enseigne", "enseigne_commerciale", "enseigne commerciale", "nom_commercial"),
            adresse=pick_first_truthy(
                "adresse_complete", "adresse", "adresse_ligne_1", "adresse_ligne1", "adresse_ligne 1",
                "adresse1", "adresse_postale", "ligne_4", "ligne4", "libelle_voie", "libelle_voie_etablissement",
                "rue", "numero_et_voie", "voie", "adresse_etablissement", "adresse2", "complement_adresse",
                "numero_voie", "adresse_geo", "adresse_complete_etablissement"
            ),
            code_postal=pick_first_truthy("code_postal", "code postal", "cp", "code_postal_etablissement", "postal"),
            commune=pick_first_truthy("commune", "ville", "localite", "libelle_commune_etablissement", "adresse_ville", "city"),
            activite_principale=pick_first_truthy("activite_principale", "code_naf", "naf", "code_ape", "ape"),
            libelle_activite=pick_first_truthy(
                "libelle_activite", "libelle activité", "libelle_naf", "activite", "activite_principale_libelle"
            ),
            tranche_effectifs=pick_first_truthy(
                "tranche_effectifs", "tranche_effectif", "tranche_effectifs_salaries", "tranche_effectif_salarie"
            ),
            effectifs_label=pick_first_truthy(
                "effectifs", "effectif", "effectifs_salaries", "effectifs salaries", "effectifs categorie",
                "effectif_salarie", "nb_salaries", "nombre_salaries", "salaries", "nombre_de_salaries",
                "effectif_total", "total_effectif", "nb_employes", "nombre_employes"
            ),
            categorie_entreprise=pick_first_truthy(
                "categorie_entreprise", "categorie", "taille_entreprise", "taille"
            ),
            est_actif=pick_bool("est_actif", "actif", "etat_etablissement", "etat"),
            est_siege=pick_bool("est_siege", "siege", "siege_social"),
        )
        session.add(inv)
        inserted += 1
    session.commit()
    return inserted

# -------- Construire le résumé 1-ligne/SIRET --------
def build_siret_summary(session: Session) -> int:
    # Récup PV en pandas (colonnes explicitement étiquetées)
    pvs_stmt = select(
        PVEvent.siret.label("siret"),
        PVEvent.cycle.label("cycle"),
        PVEvent.institution.label("institution"),
        PVEvent.date_pv.label("date_pv"),
        PVEvent.raison_sociale.label("raison_sociale"),
        PVEvent.idcc.label("idcc"),
        PVEvent.fd.label("fd"),
        PVEvent.ud.label("ud"),
        PVEvent.region.label("region"),
        PVEvent.ul.label("ul"),
        PVEvent.departement.label("departement"),
        PVEvent.cp.label("cp"),
        PVEvent.ville.label("ville"),
        PVEvent.inscrits.label("inscrits"),
        PVEvent.votants.label("votants"),
        PVEvent.sve.label("sve"),
        PVEvent.tx_participation_pv.label("tx_participation_pv"),
        PVEvent.cgt_voix.label("cgt_voix"),
        PVEvent.cfdt_voix.label("cfdt_voix"),
        PVEvent.fo_voix.label("fo_voix"),
        PVEvent.cftc_voix.label("cftc_voix"),
        PVEvent.cgc_voix.label("cgc_voix"),
        PVEvent.unsa_voix.label("unsa_voix"),
        PVEvent.sud_voix.label("sud_voix"),
        PVEvent.solidaire_voix.label("solidaire_voix"),
        PVEvent.autre_voix.label("autre_voix"),
        PVEvent.presence_cgt_pv.label("presence_cgt_pv"),
        PVEvent.pres_pv_cgt.label("pres_pv_cgt"),
        PVEvent.pres_pv_cfdt.label("pres_pv_cfdt"),
        PVEvent.pres_pv_fo.label("pres_pv_fo"),
        PVEvent.pres_pv_cftc.label("pres_pv_cftc"),
        PVEvent.pres_pv_cgc.label("pres_pv_cgc"),
        PVEvent.pres_pv_unsa.label("pres_pv_unsa"),
        PVEvent.pres_pv_sud.label("pres_pv_sud"),
        PVEvent.pres_pv_autre.label("pres_pv_autre"),
        PVEvent.compte_siret.label("compte_siret"),
        PVEvent.compte_siret_cgt.label("compte_siret_cgt"),
        PVEvent.effectif_siret.label("effectif_siret"),
        PVEvent.tranche1_effectif.label("tranche1_effectif"),
        PVEvent.tranche2_effectif.label("tranche2_effectif"),
        PVEvent.votants_siret.label("votants_siret"),
        PVEvent.nb_college_siret.label("nb_college_siret"),
        PVEvent.sve_siret.label("sve_siret"),
        PVEvent.tx_participation_siret.label("tx_participation_siret"),
        PVEvent.siret_moins_50.label("siret_moins_50"),
        PVEvent.college.label("college"),
        PVEvent.presence_cgt_siret.label("presence_cgt_siret"),
        PVEvent.pres_siret_cgt.label("pres_siret_cgt"),
        PVEvent.pres_siret_cfdt.label("pres_siret_cfdt"),
        PVEvent.pres_siret_fo.label("pres_siret_fo"),
        PVEvent.pres_siret_cftc.label("pres_siret_cftc"),
        PVEvent.pres_siret_cgc.label("pres_siret_cgc"),
        PVEvent.pres_siret_unsa.label("pres_siret_unsa"),
        PVEvent.pres_siret_sud.label("pres_siret_sud"),
        PVEvent.pres_siret_autre.label("pres_siret_autre"),
        PVEvent.pres_cgt_tous_pv_siret.label("pres_cgt_tous_pv_siret"),
        PVEvent.score_siret_cgt.label("score_siret_cgt"),
        PVEvent.score_siret_cfdt.label("score_siret_cfdt"),
        PVEvent.score_siret_fo.label("score_siret_fo"),
        PVEvent.score_siret_cftc.label("score_siret_cftc"),
        PVEvent.score_siret_cgc.label("score_siret_cgc"),
        PVEvent.score_siret_unsa.label("score_siret_unsa"),
        PVEvent.score_siret_sud.label("score_siret_sud"),
        PVEvent.score_siret_autre.label("score_siret_autre"),
        PVEvent.pct_siret_cgt.label("pct_siret_cgt"),
        PVEvent.pct_siret_cfdt.label("pct_siret_cfdt"),
        PVEvent.pct_siret_fo.label("pct_siret_fo"),
        PVEvent.pct_siret_cgc.label("pct_siret_cgc"),
        PVEvent.annee_prochain.label("annee_prochain"),
        PVEvent.date_visite_syndicat.label("date_visite_syndicat"),
        PVEvent.date_formation.label("date_formation"),
        PVEvent.code_sbf120.label("code_sbf120"),
        PVEvent.codes_sbf120_cac40.label("codes_sbf120_cac40"),
        PVEvent.est_cac40_sbf120.label("est_cac40_sbf120"),
        PVEvent.nom_groupe_sbf120.label("nom_groupe_sbf120"),
    )
    pvs = pd.read_sql(pvs_stmt, session.bind)

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
    pvs["cycle"] = pvs["cycle"].fillna("").map(_norm_cycle)

    def _to_numeric(df: pd.DataFrame, column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(dtype=float)
        series = df[column]
        if series.dtype == object:
            series = (
                series.astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".")
                .str.replace(" ", "", regex=False)
            )
        return pd.to_numeric(series, errors="coerce")

    numeric_cols = [
        "inscrits",
        "votants",
        "sve",
        "tx_participation_pv",
        "cgt_voix",
        "cfdt_voix",
        "fo_voix",
        "cftc_voix",
        "cgc_voix",
        "unsa_voix",
        "sud_voix",
        "solidaire_voix",
        "autre_voix",
        "compte_siret",
        "compte_siret_cgt",
        "effectif_siret",
        "votants_siret",
        "nb_college_siret",
        "sve_siret",
        "tx_participation_siret",
        "score_siret_cgt",
        "score_siret_cfdt",
        "score_siret_fo",
        "score_siret_cftc",
        "score_siret_cgc",
        "score_siret_unsa",
        "score_siret_sud",
        "score_siret_autre",
        "pct_siret_cgt",
        "pct_siret_cfdt",
        "pct_siret_fo",
        "pct_siret_cgc",
    ]

    for col in numeric_cols:
        if col in pvs.columns:
            pvs[col] = _to_numeric(pvs, col)

    if "institution" in pvs.columns:
        inst_series = (
            pvs["institution"].fillna("").astype(str).str.strip().str.upper()
        )
    else:
        inst_series = pd.Series([""] * len(pvs), index=pvs.index)

    carence_flag = inst_series.str.contains("CAR", na=False)
    if "votants" in pvs.columns:
        carence_flag = carence_flag | (pvs["votants"].fillna(0) <= 0)
    pvs["carence"] = carence_flag
    pvs["date_pv"] = pd.to_datetime(pvs["date_pv"], errors="coerce", dayfirst=True)

    def latest_by_cycle(df: pd.DataFrame, cycle: str, suffix: str) -> pd.DataFrame:
        subset = df[df["cycle"] == cycle].copy()
        if subset.empty:
            return pd.DataFrame(columns=["siret"])
        subset = subset.sort_values(["siret", "date_pv"], ascending=[True, True])
        subset = subset.drop_duplicates("siret", keep="last")
        subset[f"carence{suffix}"] = subset["carence"]
        rename_base = {
            "raison_sociale": f"raison_sociale{suffix}",
            "institution": f"institution{suffix}",
            "idcc": f"idcc{suffix}",
            "fd": f"fd{suffix}",
            "ud": f"ud{suffix}",
            "region": f"region{suffix}",
            "ul": f"ul{suffix}",
            "departement": f"departement{suffix}",
            "cp": f"cp{suffix}",
            "ville": f"ville{suffix}",
            "date_pv": f"date_pv{suffix}",
            "inscrits": f"inscrits{suffix}",
            "votants": f"votants{suffix}",
            "sve": f"sve{suffix}",
            "tx_participation_pv": f"tx_participation_pv{suffix}",
            "cgt_voix": f"cgt_voix{suffix}",
            "cfdt_voix": f"cfdt_voix{suffix}",
            "fo_voix": f"fo_voix{suffix}",
            "cftc_voix": f"cftc_voix{suffix}",
            "cgc_voix": f"cgc_voix{suffix}",
            "unsa_voix": f"unsa_voix{suffix}",
            "sud_voix": f"sud_voix{suffix}",
            "solidaire_voix": f"solidaire_voix{suffix}",
            "autre_voix": f"autre_voix{suffix}",
            "presence_cgt_pv": f"presence_cgt_pv{suffix}",
            "pres_pv_cgt": f"pres_pv_cgt{suffix}",
            "pres_pv_cfdt": f"pres_pv_cfdt{suffix}",
            "pres_pv_fo": f"pres_pv_fo{suffix}",
            "pres_pv_cftc": f"pres_pv_cftc{suffix}",
            "pres_pv_cgc": f"pres_pv_cgc{suffix}",
            "pres_pv_unsa": f"pres_pv_unsa{suffix}",
            "pres_pv_sud": f"pres_pv_sud{suffix}",
            "pres_pv_autre": f"pres_pv_autre{suffix}",
            "compte_siret": f"compte_siret{suffix}",
            "compte_siret_cgt": f"compte_siret_cgt{suffix}",
            "effectif_siret": f"effectif_siret{suffix}",
            "tranche1_effectif": f"tranche1_effectif{suffix}",
            "tranche2_effectif": f"tranche2_effectif{suffix}",
            "votants_siret": f"votants_siret{suffix}",
            "nb_college_siret": f"nb_college_siret{suffix}",
            "sve_siret": f"sve_siret{suffix}",
            "tx_participation_siret": f"tx_participation_siret{suffix}",
            "siret_moins_50": f"siret_moins_50{suffix}",
            "college": f"college{suffix}",
            "presence_cgt_siret": f"presence_cgt_siret{suffix}",
            "pres_siret_cgt": f"pres_siret_cgt{suffix}",
            "pres_siret_cfdt": f"pres_siret_cfdt{suffix}",
            "pres_siret_fo": f"pres_siret_fo{suffix}",
            "pres_siret_cftc": f"pres_siret_cftc{suffix}",
            "pres_siret_cgc": f"pres_siret_cgc{suffix}",
            "pres_siret_unsa": f"pres_siret_unsa{suffix}",
            "pres_siret_sud": f"pres_siret_sud{suffix}",
            "pres_siret_autre": f"pres_siret_autre{suffix}",
            "pres_cgt_tous_pv_siret": f"pres_cgt_tous_pv_siret{suffix}",
            "score_siret_cgt": f"score_siret_cgt{suffix}",
            "score_siret_cfdt": f"score_siret_cfdt{suffix}",
            "score_siret_fo": f"score_siret_fo{suffix}",
            "score_siret_cftc": f"score_siret_cftc{suffix}",
            "score_siret_cgc": f"score_siret_cgc{suffix}",
            "score_siret_unsa": f"score_siret_unsa{suffix}",
            "score_siret_sud": f"score_siret_sud{suffix}",
            "score_siret_autre": f"score_siret_autre{suffix}",
            "pct_siret_cgt": f"pct_siret_cgt{suffix}",
            "pct_siret_cfdt": f"pct_siret_cfdt{suffix}",
            "pct_siret_fo": f"pct_siret_fo{suffix}",
            "pct_siret_cgc": f"pct_siret_cgc{suffix}",
            "annee_prochain": f"annee_prochain{suffix}",
            "date_visite_syndicat": f"date_visite_syndicat{suffix}",
            "date_formation": f"date_formation{suffix}",
            "code_sbf120": f"code_sbf120{suffix}",
            "codes_sbf120_cac40": f"codes_sbf120_cac40{suffix}",
            "est_cac40_sbf120": f"est_cac40_sbf120{suffix}",
            "nom_groupe_sbf120": f"nom_groupe_sbf120{suffix}",
        }
        subset = subset.rename(columns=rename_base)
        keep_cols = ["siret"] + list(rename_base.values()) + [f"carence{suffix}"]
        return subset[keep_cols]

    last_c3 = latest_by_cycle(pvs, "C3", "_c3")
    last_c4 = latest_by_cycle(pvs, "C4", "_c4")

    # Invitations: dernière date par SIRET (filtrées C5)
    if not inv.empty:
        C5_START, C5_END = pd.to_datetime("2025-01-01"), pd.to_datetime("2028-12-31")
        inv["date_invit"] = pd.to_datetime(inv["date_invit"], errors="coerce")
        inv_c5 = inv[(inv["date_invit"] >= C5_START) & (inv["date_invit"] <= C5_END)]
        inv_latest = inv_c5.groupby("siret", as_index=False)["date_invit"].max().rename(columns={"date_invit":"date_pap_c5"})
    else:
        inv_latest = pd.DataFrame(columns=["siret","date_pap_c5"])

    # Fusion C3/C4
    base = last_c3.merge(last_c4, on="siret", how="outer")

    def ensure_series(column: str, default=None):
        if column in base.columns:
            return base[column]
        return pd.Series(default, index=base.index)

    def coalesce(col_c4: str, col_c3: str):
        vals_c4 = base.get(col_c4)
        vals_c3 = base.get(col_c3)
        if vals_c4 is None and vals_c3 is None:
            return pd.Series([None] * len(base), index=base.index)
        if vals_c4 is None:
            return vals_c3
        if vals_c3 is None:
            return vals_c4
        return vals_c4.fillna(vals_c3)

    base["raison_sociale"] = coalesce("raison_sociale_c4", "raison_sociale_c3")
    base["idcc"] = coalesce("idcc_c4", "idcc_c3")
    base["fd_c3"] = ensure_series("fd_c3")
    base["fd_c4"] = ensure_series("fd_c4")
    base["ud_c3"] = ensure_series("ud_c3")
    base["ud_c4"] = ensure_series("ud_c4")
    base["region"] = coalesce("region_c4", "region_c3")
    base["ul"] = coalesce("ul_c4", "ul_c3")
    base["dep"] = coalesce("departement_c4", "departement_c3")
    base["cp"] = coalesce("cp_c4", "cp_c3")
    base["ville"] = coalesce("ville_c4", "ville_c3")

    date_c3 = ensure_series("date_pv_c3")
    date_c4 = ensure_series("date_pv_c4")

    base["statut_pap"] = np.where(
        date_c3.notna() & date_c4.notna(),
        "C3+C4",
        np.where(
            date_c4.notna(),
            "C4",
            np.where(date_c3.notna(), "C3", "Aucun"),
        ),
    )

    for col in ("date_pv_c3", "date_pv_c4"):
        if col in base.columns:
            base[col] = pd.to_datetime(base[col], errors="coerce")
    available_dates = [col for col in ("date_pv_c3", "date_pv_c4") if col in base.columns]
    if available_dates:
        base["date_pv_max"] = base[available_dates].max(axis=1)
    else:
        base["date_pv_max"] = pd.Series([pd.NaT] * len(base), index=base.index)

    for suffix in ("_c3", "_c4"):
        col = f"carence{suffix}"
        if col in base.columns:
            base[col] = base[col].fillna(False)

    cgt_c3 = ensure_series("cgt_voix_c3", 0).fillna(0)
    cgt_c4 = ensure_series("cgt_voix_c4", 0).fillna(0)
    base["cgt_implantee"] = (cgt_c3 > 0) | (cgt_c4 > 0)

    # Informations agrégées (priorité au C4)
    def prefer_c4(col: str):
        return coalesce(f"{col}_c4", f"{col}_c3")

    base["effectif_siret"] = prefer_c4("effectif_siret")
    base["tranche1_effectif"] = prefer_c4("tranche1_effectif")
    base["tranche2_effectif"] = prefer_c4("tranche2_effectif")
    base["siret_moins_50"] = prefer_c4("siret_moins_50")
    base["nb_college_siret"] = prefer_c4("nb_college_siret")
    base["sve_siret"] = prefer_c4("sve_siret")
    base["tx_participation_siret"] = prefer_c4("tx_participation_siret")
    base["presence_cgt_siret"] = prefer_c4("presence_cgt_siret")
    base["pres_siret_cgt"] = prefer_c4("pres_siret_cgt")
    base["pres_siret_cfdt"] = prefer_c4("pres_siret_cfdt")
    base["pres_siret_fo"] = prefer_c4("pres_siret_fo")
    base["pres_siret_cftc"] = prefer_c4("pres_siret_cftc")
    base["pres_siret_cgc"] = prefer_c4("pres_siret_cgc")
    base["pres_siret_unsa"] = prefer_c4("pres_siret_unsa")
    base["pres_siret_sud"] = prefer_c4("pres_siret_sud")
    base["pres_siret_autre"] = prefer_c4("pres_siret_autre")
    base["pres_cgt_tous_pv_siret"] = prefer_c4("pres_cgt_tous_pv_siret")
    base["score_siret_cgt"] = prefer_c4("score_siret_cgt")
    base["score_siret_cfdt"] = prefer_c4("score_siret_cfdt")
    base["score_siret_fo"] = prefer_c4("score_siret_fo")
    base["score_siret_cftc"] = prefer_c4("score_siret_cftc")
    base["score_siret_cgc"] = prefer_c4("score_siret_cgc")
    base["score_siret_unsa"] = prefer_c4("score_siret_unsa")
    base["score_siret_sud"] = prefer_c4("score_siret_sud")
    base["score_siret_autre"] = prefer_c4("score_siret_autre")
    base["pct_siret_cgt"] = prefer_c4("pct_siret_cgt")
    base["pct_siret_cfdt"] = prefer_c4("pct_siret_cfdt")
    base["pct_siret_fo"] = prefer_c4("pct_siret_fo")
    base["pct_siret_cgc"] = prefer_c4("pct_siret_cgc")
    base["compte_siret"] = prefer_c4("compte_siret")
    base["compte_siret_cgt"] = prefer_c4("compte_siret_cgt")
    base["votants_siret"] = prefer_c4("votants_siret")
    base["annee_prochain"] = prefer_c4("annee_prochain")
    base["date_visite_syndicat"] = prefer_c4("date_visite_syndicat")
    base["date_formation"] = prefer_c4("date_formation")
    base["code_sbf120"] = prefer_c4("code_sbf120")
    base["codes_sbf120_cac40"] = prefer_c4("codes_sbf120_cac40")
    base["est_cac40_sbf120"] = prefer_c4("est_cac40_sbf120")
    base["nom_groupe_sbf120"] = prefer_c4("nom_groupe_sbf120")

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
        "region": base.get("region"),
        "ul": base.get("ul"),
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
        "cfdt_voix_c3": base.get("cfdt_voix_c3"),
        "cfdt_voix_c4": base.get("cfdt_voix_c4"),
        "fo_voix_c3": base.get("fo_voix_c3"),
        "fo_voix_c4": base.get("fo_voix_c4"),
        "cftc_voix_c3": base.get("cftc_voix_c3"),
        "cftc_voix_c4": base.get("cftc_voix_c4"),
        "cgc_voix_c3": base.get("cgc_voix_c3"),
        "cgc_voix_c4": base.get("cgc_voix_c4"),
        "unsa_voix_c3": base.get("unsa_voix_c3"),
        "unsa_voix_c4": base.get("unsa_voix_c4"),
        "sud_voix_c3": base.get("sud_voix_c3"),
        "sud_voix_c4": base.get("sud_voix_c4"),
        "solidaire_voix_c3": base.get("solidaire_voix_c3"),
        "solidaire_voix_c4": base.get("solidaire_voix_c4"),
        "autre_voix_c3": base.get("autre_voix_c3"),
        "autre_voix_c4": base.get("autre_voix_c4"),
        "statut_pap": base["statut_pap"],
        "date_pv_max": safe_pv_max,
        "date_pap_c5": base.get("date_pap_c5"),
        "cgt_implantee": base["cgt_implantee"],
        "effectif_siret": base.get("effectif_siret"),
        "tranche1_effectif": base.get("tranche1_effectif"),
        "tranche2_effectif": base.get("tranche2_effectif"),
        "siret_moins_50": base.get("siret_moins_50"),
        "nb_college_siret": base.get("nb_college_siret"),
        "score_siret_cgt": base.get("score_siret_cgt"),
        "score_siret_cfdt": base.get("score_siret_cfdt"),
        "score_siret_fo": base.get("score_siret_fo"),
        "score_siret_cftc": base.get("score_siret_cftc"),
        "score_siret_cgc": base.get("score_siret_cgc"),
        "score_siret_unsa": base.get("score_siret_unsa"),
        "score_siret_sud": base.get("score_siret_sud"),
        "score_siret_autre": base.get("score_siret_autre"),
        "pct_siret_cgt": base.get("pct_siret_cgt"),
        "pct_siret_cfdt": base.get("pct_siret_cfdt"),
        "pct_siret_fo": base.get("pct_siret_fo"),
        "pct_siret_cgc": base.get("pct_siret_cgc"),
        "presence_cgt_siret": base.get("presence_cgt_siret"),
        "pres_siret_cgt": base.get("pres_siret_cgt"),
        "pres_siret_cfdt": base.get("pres_siret_cfdt"),
        "pres_siret_fo": base.get("pres_siret_fo"),
        "pres_siret_cftc": base.get("pres_siret_cftc"),
        "pres_siret_cgc": base.get("pres_siret_cgc"),
        "pres_siret_unsa": base.get("pres_siret_unsa"),
        "pres_siret_sud": base.get("pres_siret_sud"),
        "pres_siret_autre": base.get("pres_siret_autre"),
        "pres_cgt_tous_pv_siret": base.get("pres_cgt_tous_pv_siret"),
        "tx_participation_siret": base.get("tx_participation_siret"),
        "sve_siret": base.get("sve_siret"),
        "compte_siret": base.get("compte_siret"),
        "compte_siret_cgt": base.get("compte_siret_cgt"),
        "votants_siret": base.get("votants_siret"),
        "annee_prochain": base.get("annee_prochain"),
        "date_visite_syndicat": base.get("date_visite_syndicat"),
        "date_formation": base.get("date_formation"),
        "code_sbf120": base.get("code_sbf120"),
        "codes_sbf120_cac40": base.get("codes_sbf120_cac40"),
        "est_cac40_sbf120": base.get("est_cac40_sbf120"),
        "nom_groupe_sbf120": base.get("nom_groupe_sbf120"),
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
