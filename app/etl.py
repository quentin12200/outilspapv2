import pandas as pd, numpy as np, re, unicodedata
import logging
from dateutil.parser import parse as dtparse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from datetime import datetime, date
from .models import PVEvent, Invitation, SiretSummary

logger = logging.getLogger(__name__)

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
    """Normalise une valeur de SIRET en ne conservant que les chiffres."""

    if pd.isna(x):
        return None
    s = re.sub(r"\D", "", str(x))
    if not s:
        return None
    s = s.lstrip("0")
    return s or None


def _normalize_siret_series(series: pd.Series | None) -> pd.Series | None:
    """Normalise une série contenant des SIRET en conservant uniquement les chiffres."""

    if series is None:
        return None

    normalized = series.map(_to14)
    return normalized

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

def get_nombre_sieges(effectif: int) -> int:
    """
    Retourne le nombre de sièges titulaires au CSE selon l'effectif,
    conformément au tableau officiel du Code du travail.
    """
    if effectif is None:
        return None

    # Tableau officiel : (effectif_min, effectif_max, nb_sieges)
    tranches = [
        (11, 24, 1),
        (25, 49, 2),
        (50, 74, 4),
        (75, 99, 5),
        (100, 124, 6),
        (125, 149, 7),
        (150, 174, 8),
        (175, 199, 9),
        (200, 249, 10),
        (250, 299, 11),
        (300, 399, 11),
        (400, 499, 12),
        (500, 599, 13),
        (600, 699, 13),
        (700, 799, 14),
        (800, 899, 14),
        (900, 999, 15),
        (1000, 1249, 15),
        (1250, 1499, 17),
        (1500, 1749, 18),
        (1750, 1999, 19),
        (2000, 2249, 20),
        (2250, 2499, 21),
        (2500, 2749, 22),
        (2750, 2999, 22),
        (3000, 3249, 23),
        (3250, 3499, 23),
        (3500, 3749, 24),
        (3750, 3999, 24),
        (4000, 4249, 24),
        (4250, 4499, 25),
        (4500, 4749, 25),
        (4750, 4999, 25),
        (5000, 5499, 26),
        (5500, 5999, 26),
        (6000, 6499, 27),
        (6500, 6999, 27),
        (7000, 7499, 28),
        (7500, 7999, 29),
        (8000, 8499, 29),
        (8500, 8999, 30),
        (9000, 9999, 34),
    ]

    # Si effectif >= 10000, retourner 35 sièges
    if effectif >= 10000:
        return 35

    # Recherche dans les tranches
    for min_eff, max_eff, sieges in tranches:
        if min_eff <= effectif <= max_eff:
            return sieges

    # Si effectif < 11, pas de CSE
    return None

def calcul_repartition_sieges(inscrits: int, votants: int, blancs_nuls: int, voix_par_orga: dict) -> dict:
    """
    Calcule la répartition des sièges selon le système du quotient électoral
    et de la plus forte moyenne (méthode officielle).

    Args:
        inscrits: Nombre d'inscrits
        votants: Nombre de votants
        blancs_nuls: Nombre de votes blancs et nuls
        voix_par_orga: Dictionnaire {organisation: nombre_de_voix}

    Returns:
        Dictionnaire {organisation: nombre_de_sieges}
    """
    # Initialiser les sièges à 0 pour toutes les organisations
    sieges_par_orga = {orga: 0 for orga in voix_par_orga.keys()}

    # Filtrer les listes qui ont des voix
    listes_actives = {orga: voix for orga, voix in voix_par_orga.items() if voix and voix > 0}

    if not listes_actives:
        return sieges_par_orga

    # Déterminer le nombre total de sièges à pourvoir
    nb_sieges_total = get_nombre_sieges(inscrits)
    if nb_sieges_total is None or nb_sieges_total == 0:
        return sieges_par_orga

    # Calculer les suffrages valablement exprimés (SVE)
    sve = votants - (blancs_nuls or 0)
    if sve <= 0:
        return sieges_par_orga

    # Calculer le quotient électoral
    quotient = sve / nb_sieges_total

    # ÉTAPE 1: Attribution directe au quotient
    for orga, voix in listes_actives.items():
        sieges = int(voix / quotient)  # Partie entière
        sieges_par_orga[orga] = sieges

    # ÉTAPE 2: Répartition des sièges restants à la plus forte moyenne
    sieges_attribues = sum(sieges_par_orga.values())
    sieges_restants = nb_sieges_total - sieges_attribues

    while sieges_restants > 0:
        # Calculer la moyenne pour chaque liste si elle recevait un siège supplémentaire
        moyennes = {}
        for orga, voix in listes_actives.items():
            moyennes[orga] = voix / (sieges_par_orga[orga] + 1)

        # Attribuer le siège à la liste avec la plus forte moyenne
        orga_gagnante = max(moyennes, key=moyennes.get)
        sieges_par_orga[orga_gagnante] += 1
        sieges_restants -= 1

    return sieges_par_orga

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


def _normalize_numeric_series(series: pd.Series) -> pd.Series:
    """Convertit une série en valeurs numériques fiables.

    Les fichiers Excel fournis dans la release contiennent souvent des
    séparateurs d'espace (\u00a0, espaces fines, etc.) pour les milliers.
    Lors de l'import, ces valeurs deviennent des chaînes comme ``"1 200"`` ou
    ``"1\u202f500"`` qui ne peuvent pas être converties directement en
    nombres. Cette fonction supprime ces séparateurs et remplace les virgules
    par des points avant de faire ``pd.to_numeric``.
    """

    if series is None or getattr(series, "empty", False):
        return series

    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = (
        series.astype(str)
        .str.replace("\u202f", "", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    cleaned = cleaned.str.replace(r"[^0-9.+-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")

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

        def pick_int(*keys: str) -> int | None:
            value = pick(*keys)
            if value is None:
                return None
            try:
                return int(float(str(value).replace(",", ".").strip()))
            except:
                return None

        def pick_date(*keys: str) -> date | None:
            value = pick(*keys)
            if value is None:
                return None
            return _todate(value)

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
            # Colonnes manuelles pour ajout PAP
            ud=pick_first_truthy("ud", "union_departementale", "union departementale", "departement", "dep"),
            fd=pick_first_truthy("fd", "federation", "fédération"),
            idcc=pick_first_truthy("idcc", "code_idcc", "convention_collective"),
            effectif_connu=pick_int("effectif_connu", "effectif connu", "effectif_manuel", "effectif manuel"),
            date_reception=pick_date("date_reception", "date reception", "date_de_reception", "date de reception"),
            date_election=pick_date("date_election", "date election", "date_des_elections", "date des elections", "date_scrutin", "date scrutin"),
            structure_saisie=pick_first_truthy("structure_saisie", "structure saisie", "structure", "organisation"),
        )
        session.add(inv)
        inserted += 1
    session.commit()
    return inserted

# -------- Construire le résumé 1-ligne/SIRET --------
def build_siret_summary(session: Session) -> int:
    # Récup PV en pandas (seulement les colonnes nécessaires, nommées explicitement)
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
        PVEvent.cp.label("cp"),
        PVEvent.ville.label("ville"),
        PVEvent.inscrits.label("inscrits"),
        PVEvent.votants.label("votants"),
        PVEvent.sve.label("sve"),
        PVEvent.cgt_voix.label("cgt_voix"),
        PVEvent.cfdt_voix.label("cfdt_voix"),
        PVEvent.fo_voix.label("fo_voix"),
        PVEvent.cftc_voix.label("cftc_voix"),
        PVEvent.cgc_voix.label("cgc_voix"),
        PVEvent.unsa_voix.label("unsa_voix"),
        PVEvent.sud_voix.label("sud_voix"),
        PVEvent.solidaire_voix.label("solidaire_voix"),
        PVEvent.autre_voix.label("autre_voix"),
    )
    pvs = pd.read_sql(pvs_stmt, session.bind)

    if "siret" in pvs.columns:
        pvs["siret"] = _normalize_siret_series(pvs["siret"])
        pvs = pvs[pvs["siret"].notna()].copy()

    numeric_columns = [
        "inscrits",
        "votants",
        "sve",
        "cgt_voix",
        "cfdt_voix",
        "fo_voix",
        "cftc_voix",
        "cgc_voix",
        "unsa_voix",
        "sud_voix",
        "solidaire_voix",
        "autre_voix",
    ]
    for col in numeric_columns:
        if col in pvs.columns:
            pvs[col] = _normalize_numeric_series(pvs[col])

    inv_latest = pd.DataFrame(columns=["siret", "date_pap_c5"])
    inv_latest_map: dict[str, date | None] = {}

    try:
        inv_stmt = session.query(Invitation).statement
        inv = pd.read_sql(inv_stmt, session.bind)
        if "siret" in inv.columns:
            inv["siret"] = _normalize_siret_series(inv["siret"])
            inv = inv[inv["siret"].notna()].copy()
    except OperationalError:
        inv = pd.DataFrame()

    if pvs.empty:
        session.query(SiretSummary).delete()
        session.commit()
        return 0

    if not inv.empty:
        inv["date_invit"] = pd.to_datetime(inv["date_invit"], errors="coerce")
        valid_inv = inv[inv["date_invit"].notna()].copy()
        if not valid_inv.empty:
            valid_inv["date_pap_c5"] = valid_inv["date_invit"].dt.date
            inv_latest = (
                valid_inv
                .sort_values(["siret", "date_invit"], ascending=[True, False])
                .drop_duplicates(subset="siret", keep="first")
                [["siret", "date_pap_c5"]]
            )
            inv_latest_map = dict(zip(inv_latest["siret"], inv_latest["date_pap_c5"]))

    def last_per_cycle(mask):
        subset = pvs.loc[mask].copy()
        if subset.empty:
            return subset
        subset = subset.sort_values(["siret", "date_pv"], ascending=[True, False])
        return subset.drop_duplicates(subset="siret", keep="first")

    # Normaliser
    pvs["cycle"] = pvs["cycle"].fillna("").astype(str).str.upper().str.strip()
    type_series = pvs.get("type")
    if type_series is None:
        type_series = pvs.get("institution")
    if type_series is None:
        type_series = pd.Series(["" for _ in range(len(pvs))])
    pvs["carence"] = type_series.fillna("").astype(str).str.lower().str.contains("car")
    if "votants" in pvs.columns:
        pvs.loc[pvs["votants"].fillna(0) <= 0, "carence"] = True
    # Filtrage bornes cycles
    C3_START, C3_END = pd.to_datetime("2017-01-01"), pd.to_datetime("2020-12-31")
    C4_START, C4_END = pd.to_datetime("2021-01-01"), pd.to_datetime("2024-12-31")
    C5_START, C5_END = pd.to_datetime("2025-01-01"), pd.to_datetime("2028-12-31")
    pvs["date_pv"] = pd.to_datetime(pvs["date_pv"], errors="coerce")
    mask_c3 = (pvs["cycle"]=="C3") & (pvs["date_pv"] >= C3_START) & (pvs["date_pv"] <= C3_END)
    mask_c4 = (pvs["cycle"]=="C4") & (pvs["date_pv"] >= C4_START) & (pvs["date_pv"] <= C4_END)
    last_c3 = last_per_cycle(mask_c3)
    last_c4 = last_per_cycle(mask_c4)

    # Invitations: dernière date par SIRET.
    #
    # L'ancien code filtrait strictement les dates sur la plage 2025-2028 en partant
    # du principe que toutes les invitations référencées seraient uniquement C5.
    # En pratique, les fichiers importés contiennent des invitations datées dès 2022
    # (voire plus tôt) mais toujours liées au cycle 5. Ce filtrage supprimait donc
    # toutes les lignes et empêchait l'alimentation de `date_pap_c5`, d'où un
    # tableau "Invitations PAP - Cycle 5" vide.
    #
    # On remonte désormais la dernière date valide quel que soit l'année ; cela
    # garantit que la table récapitulative reflète bien les données importées tout
    # en conservant la possibilité de filtrer côté interface.
    # Fusion C3/C4
    base = last_c3.merge(last_c4, on="siret", how="outer", suffixes=("_c3","_c4"))

    # Colonnes consolidées
    base["raison_sociale"] = base["raison_sociale_c4"].fillna(base["raison_sociale_c3"])
    base["idcc"] = base["idcc_c4"].fillna(base["idcc_c3"])

    numeric_suffixes = [
        "inscrits",
        "votants",
        "sve",
        "cgt_voix",
        "cfdt_voix",
        "fo_voix",
        "cftc_voix",
        "cgc_voix",
        "unsa_voix",
        "sud_voix",
        "solidaire_voix",
        "autre_voix",
    ]
    for suffix in numeric_suffixes:
        col_c3 = f"{suffix}_c3"
        col_c4 = f"{suffix}_c4"
        if col_c3 in base.columns:
            base[col_c3] = _normalize_numeric_series(base[col_c3])
        if col_c4 in base.columns:
            base[col_c4] = _normalize_numeric_series(base[col_c4])

    # TODO: Calculer les sièges pour C3 et C4 en utilisant le quotient électoral
    # TEMPORAIREMENT DÉSACTIVÉ car trop lent sur 126k lignes (cause timeout/OOM)
    # On initialisera les colonnes à None pour l'instant
    logger.warning("⚠️  Seat calculation temporarily disabled (performance issue with 126k+ rows)")
    for cycle in ["c3", "c4"]:
        for org in ["cgt", "cfdt", "fo", "cftc", "cgc", "unsa", "sud", "autre"]:
            base[f"{org}_siege_{cycle}"] = None

    def _series_or_empty(name: str):
        if name in base.columns:
            return base[name]
        return pd.Series([None] * len(base), index=base.index)

    if "departement_c4" in base.columns or "departement_c3" in base.columns:
        base["dep"] = _series_or_empty("departement_c4").fillna(_series_or_empty("departement_c3"))
    else:
        base["dep"] = _series_or_empty("ud_c4").fillna(_series_or_empty("ud_c3"))

    base["region"] = _series_or_empty("region_c4").fillna(_series_or_empty("region_c3"))
    base["ul"] = _series_or_empty("ul_c4").fillna(_series_or_empty("ul_c3"))
    base["cp"] = base["cp_c4"].fillna(base["cp_c3"])
    base["ville"] = base["ville_c4"].fillna(base["ville_c3"])

    base["statut_pap"] = np.where(base["date_pv_c3"].notna() & base["date_pv_c4"].notna(), "C3+C4",
                           np.where(base["date_pv_c4"].notna(), "C4",
                             np.where(base["date_pv_c3"].notna(), "C3", "Aucun")))
    # Correction : conversion explicite en datetime64
    base["date_pv_c3"] = pd.to_datetime(base["date_pv_c3"], errors="coerce")
    base["date_pv_c4"] = pd.to_datetime(base["date_pv_c4"], errors="coerce")
    base["date_pv_max"] = base[["date_pv_c3","date_pv_c4"]].max(axis=1)

    # Implantation CGT si voix > 0 en C4 uniquement
    base["cgt_implantee"] = (base["cgt_voix_c4"].fillna(0) > 0)

    # Joindre invitations
    base = base.merge(inv_latest, on="siret", how="left")

    if "date_pap_c5" in base.columns:
        existing_dates = pd.to_datetime(base["date_pap_c5"], errors="coerce").dt.date
    else:
        existing_dates = pd.Series([None] * len(base), index=base.index)

    mapped_dates = base["siret"].map(inv_latest_map)
    base["date_pap_c5"] = mapped_dates.where(mapped_dates.notna(), existing_dates)

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
        "cgt_siege_c3": base.get("cgt_siege_c3"),
        "cgt_siege_c4": base.get("cgt_siege_c4"),
        "cfdt_siege_c3": base.get("cfdt_siege_c3"),
        "cfdt_siege_c4": base.get("cfdt_siege_c4"),
        "fo_siege_c3": base.get("fo_siege_c3"),
        "fo_siege_c4": base.get("fo_siege_c4"),
        "cftc_siege_c3": base.get("cftc_siege_c3"),
        "cftc_siege_c4": base.get("cftc_siege_c4"),
        "cgc_siege_c3": base.get("cgc_siege_c3"),
        "cgc_siege_c4": base.get("cgc_siege_c4"),
        "unsa_siege_c3": base.get("unsa_siege_c3"),
        "unsa_siege_c4": base.get("unsa_siege_c4"),
        "sud_siege_c3": base.get("sud_siege_c3"),
        "sud_siege_c4": base.get("sud_siege_c4"),
        "autre_siege_c3": base.get("autre_siege_c3"),
        "autre_siege_c4": base.get("autre_siege_c4"),
        "statut_pap": base["statut_pap"],
        "date_pv_max": safe_pv_max,
        "date_pap_c5": base.get("date_pap_c5"),
        "cgt_implantee": base["cgt_implantee"]
    })

    if "date_pap_c5" in out.columns:
        out["date_pap_c5"] = pd.to_datetime(out["date_pap_c5"], errors="coerce").dt.date

    int_columns = [
        "inscrits_c3",
        "inscrits_c4",
        "votants_c3",
        "votants_c4",
        "cgt_voix_c3",
        "cgt_voix_c4",
        "cfdt_voix_c3",
        "cfdt_voix_c4",
        "fo_voix_c3",
        "fo_voix_c4",
        "cftc_voix_c3",
        "cftc_voix_c4",
        "cgc_voix_c3",
        "cgc_voix_c4",
        "unsa_voix_c3",
        "unsa_voix_c4",
        "sud_voix_c3",
        "sud_voix_c4",
        "solidaire_voix_c3",
        "solidaire_voix_c4",
        "autre_voix_c3",
        "autre_voix_c4",
        "cgt_siege_c3",
        "cgt_siege_c4",
        "cfdt_siege_c3",
        "cfdt_siege_c4",
        "fo_siege_c3",
        "fo_siege_c4",
        "cftc_siege_c3",
        "cftc_siege_c4",
        "cgc_siege_c3",
        "cgc_siege_c4",
        "unsa_siege_c3",
        "unsa_siege_c4",
        "sud_siege_c3",
        "sud_siege_c4",
        "autre_siege_c3",
        "autre_siege_c4",
    ]
    for col in int_columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round().astype("Int64")


    # Reset table (simple & robuste)
    session.execute(SiretSummary.__table__.delete())
    session.commit()

    # Bulk-insert
    out = out.where(pd.notna(out), None)

    def nan_to_none(val):
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        return val

    records = out.to_dict(orient="records")
    rows = [{k: nan_to_none(v) for k, v in row.items()} for row in records]

    if not rows:
        return 0

    chunk_size = 2000
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start:start + chunk_size]
        session.execute(SiretSummary.__table__.insert(), chunk)
        session.commit()

    return len(rows)
