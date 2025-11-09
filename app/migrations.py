# app/migrations.py
"""
Migrations automatiques pour ajouter les colonnes manquantes.
Ce script s'exécute au démarrage de l'application.
"""

import logging
from sqlalchemy import text, inspect
from .db import engine

logger = logging.getLogger(__name__)

# Colonnes Sirene à ajouter à la table invitations
SIRENE_COLUMNS = [
    ("denomination", "TEXT"),
    ("enseigne", "TEXT"),
    ("adresse", "TEXT"),
    ("code_postal", "VARCHAR(10)"),
    ("commune", "TEXT"),
    ("activite_principale", "VARCHAR(10)"),
    ("libelle_activite", "TEXT"),
    ("tranche_effectifs", "VARCHAR(5)"),
    ("effectifs_label", "TEXT"),
    ("est_siege", "BOOLEAN"),
    ("est_actif", "BOOLEAN"),
    ("categorie_entreprise", "VARCHAR(10)"),
    ("date_enrichissement", "DATETIME"),
]

# Colonnes pour ajout manuel d'invitations PAP
MANUAL_INVITATION_COLUMNS = [
    ("ud", "VARCHAR(80)"),
    ("fd", "VARCHAR(80)"),
    ("idcc", "VARCHAR(20)"),
    ("idcc_url", "TEXT"),
    ("effectif_connu", "INTEGER"),
    ("date_reception", "DATE"),
    ("date_election", "DATE"),
    ("structure_saisie", "TEXT"),
]

# Nouvelles colonnes pour pv_events (v1.0.0 - scores syndicaux complets)
PV_EVENTS_NEW_COLUMNS = [
    ("id_pv", "VARCHAR(50)"),
    ("region", "VARCHAR(100)"),
    ("ul", "VARCHAR(100)"),
    ("institution", "VARCHAR(100)"),
    ("oetamic", "VARCHAR(100)"),
    ("deno_coll", "TEXT"),
    ("duree_mandat", "INTEGER"),
    ("date_prochain_scrutin", "DATE"),
    ("quadrimestre_scrutin", "VARCHAR(20)"),
    ("controle", "VARCHAR(50)"),
    ("date_visite_syndicat", "DATE"),
    ("date_formation", "DATE"),
    ("college", "VARCHAR(100)"),
    ("compo_college", "TEXT"),
    ("sve", "INTEGER"),
    ("tx_participation_pv", "REAL"),
    # Scores syndicaux
    ("cfdt_voix", "INTEGER"),
    ("fo_voix", "INTEGER"),
    ("cftc_voix", "INTEGER"),
    ("cgc_voix", "INTEGER"),
    ("unsa_voix", "INTEGER"),
    ("solidaire_voix", "INTEGER"),
    ("autre_voix", "INTEGER"),
    # Présence syndicats PV
    ("pres_pv_cgt", "BOOLEAN"),
    ("pres_pv_cfdt", "BOOLEAN"),
    ("pres_pv_fo", "BOOLEAN"),
    ("pres_pv_cftc", "BOOLEAN"),
    ("pres_pv_cgc", "BOOLEAN"),
    ("pres_pv_unsa", "BOOLEAN"),
    ("pres_pv_sud", "BOOLEAN"),
    ("pres_pv_autre", "BOOLEAN"),
    # Composition effectifs
    ("ouvriers", "INTEGER"),
    ("employes", "INTEGER"),
    ("techniciens", "INTEGER"),
    ("maitrises", "INTEGER"),
    ("ingenieurs", "INTEGER"),
    ("cadres", "INTEGER"),
    ("pct_inscrits_ictam", "REAL"),
    # Agrégations SIRET
    ("compte_siret", "INTEGER"),
    ("compte_siret_cgt", "INTEGER"),
    ("effectif_siret", "INTEGER"),
    ("tranche1_effectif", "VARCHAR(50)"),
    ("tranche2_effectif", "VARCHAR(50)"),
    ("votants_siret", "INTEGER"),
    ("nb_college_siret", "INTEGER"),
    ("sve_siret", "INTEGER"),
    ("tx_participation_siret", "REAL"),
    ("siret_moins_50", "BOOLEAN"),
    ("presence_cgt_siret", "BOOLEAN"),
    ("pres_cgt_tous_pv_siret", "BOOLEAN"),
    # Scores SIRET agrégés
    ("score_siret_cgt", "INTEGER"),
    ("score_siret_cfdt", "INTEGER"),
    ("score_siret_fo", "INTEGER"),
    ("score_siret_cftc", "INTEGER"),
    ("score_siret_cgc", "INTEGER"),
    ("score_siret_unsa", "INTEGER"),
    ("score_siret_sud", "INTEGER"),
    ("score_siret_autre", "INTEGER"),
    # Présence SIRET agrégée
    ("pres_siret_cgt", "BOOLEAN"),
    ("pres_siret_cfdt", "BOOLEAN"),
    ("pres_siret_fo", "BOOLEAN"),
    ("pres_siret_cftc", "BOOLEAN"),
    ("pres_siret_cgc", "BOOLEAN"),
    ("pres_siret_unsa", "BOOLEAN"),
    ("pres_siret_sud", "BOOLEAN"),
    ("pres_siret_autre", "BOOLEAN"),
    # Pourcentages SIRET
    ("pct_siret_cgt", "REAL"),
    ("pct_siret_cfdt", "REAL"),
    ("pct_siret_fo", "REAL"),
    ("pct_siret_cgc", "REAL"),
    # Infos SIREN
    ("siren", "VARCHAR(9)"),
    ("effectif_siren", "INTEGER"),
    ("tranche_effectif_siren", "VARCHAR(50)"),
    ("compte_siren", "INTEGER"),
    ("siren_votants", "INTEGER"),
    ("siren_sve", "INTEGER"),
    ("siren_voix_cgt", "INTEGER"),
    ("siren_score_cgt", "REAL"),
    ("siren_voix_cfdt", "INTEGER"),
    ("siren_voix_fo", "INTEGER"),
    ("siren_voix_cftc", "INTEGER"),
    ("siren_voix_cgc", "INTEGER"),
    # Infos RED
    ("idcc_red", "VARCHAR(20)"),
    ("fd_code", "VARCHAR(20)"),
    ("cr_code", "VARCHAR(20)"),
    # CAC40/SBF120
    ("code_sbf120", "VARCHAR(50)"),
    ("codes_sbf120_cac40", "VARCHAR(100)"),
    ("est_cac40_sbf120", "VARCHAR(10)"),
    ("nom_groupe_sbf120", "TEXT"),
    # Divers
    ("annee_prochain", "INTEGER"),
    ("binaire", "VARCHAR(50)"),
]

# Nouvelles colonnes pour siret_summary (v1.0.0 - scores syndicaux)
SIRET_SUMMARY_NEW_COLUMNS = [
    ("region", "VARCHAR(100)"),
    ("ul", "VARCHAR(100)"),
    # Cycle 3 - autres syndicats
    ("cfdt_voix_c3", "INTEGER"),
    ("fo_voix_c3", "INTEGER"),
    ("cftc_voix_c3", "INTEGER"),
    ("cgc_voix_c3", "INTEGER"),
    ("unsa_voix_c3", "INTEGER"),
    ("sud_voix_c3", "INTEGER"),
    ("solidaire_voix_c3", "INTEGER"),
    ("autre_voix_c3", "INTEGER"),
    # Cycle 4 - autres syndicats
    ("cfdt_voix_c4", "INTEGER"),
    ("fo_voix_c4", "INTEGER"),
    ("cftc_voix_c4", "INTEGER"),
    ("cgc_voix_c4", "INTEGER"),
    ("unsa_voix_c4", "INTEGER"),
    ("sud_voix_c4", "INTEGER"),
    ("solidaire_voix_c4", "INTEGER"),
    ("autre_voix_c4", "INTEGER"),
    # Infos SIRET
    ("effectif_siret", "INTEGER"),
    ("tranche1_effectif", "VARCHAR(50)"),
    ("tranche2_effectif", "VARCHAR(50)"),
    ("siret_moins_50", "BOOLEAN"),
    ("nb_college_siret", "INTEGER"),
    # Scores agrégés tous cycles
    ("score_siret_cgt", "INTEGER"),
    ("score_siret_cfdt", "INTEGER"),
    ("score_siret_fo", "INTEGER"),
    ("score_siret_cftc", "INTEGER"),
    ("score_siret_cgc", "INTEGER"),
    ("score_siret_unsa", "INTEGER"),
    ("score_siret_sud", "INTEGER"),
    ("score_siret_autre", "INTEGER"),
    # Pourcentages SIRET
    ("pct_siret_cgt", "REAL"),
    ("pct_siret_cfdt", "REAL"),
    ("pct_siret_fo", "REAL"),
    ("pct_siret_cgc", "REAL"),
    # Présence syndicats
    ("presence_cgt_siret", "BOOLEAN"),
    ("pres_siret_cgt", "BOOLEAN"),
    ("pres_siret_cfdt", "BOOLEAN"),
    ("pres_siret_fo", "BOOLEAN"),
    ("pres_siret_cftc", "BOOLEAN"),
    ("pres_siret_cgc", "BOOLEAN"),
    ("pres_siret_unsa", "BOOLEAN"),
    ("pres_siret_sud", "BOOLEAN"),
    ("pres_siret_autre", "BOOLEAN"),
    # Infos SIREN
    ("siren", "VARCHAR(9)"),
    ("effectif_siren", "INTEGER"),
    ("tranche_effectif_siren", "VARCHAR(50)"),
    ("siren_score_cgt", "REAL"),
    # CAC40/SBF120
    ("est_cac40_sbf120", "VARCHAR(10)"),
    ("nom_groupe_sbf120", "TEXT"),
]


def column_exists(table_name: str, column_name: str) -> bool:
    """Vérifie si une colonne existe dans une table."""
    inspector = inspect(engine)

    # Vérifie si la table existe
    if table_name not in inspector.get_table_names():
        return False

    # Récupère les colonnes de la table
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_columns_to_table(table_name: str, columns_def: list):
    """
    Ajoute des colonnes à une table si elles n'existent pas déjà.

    Args:
        table_name: Nom de la table
        columns_def: Liste de tuples (column_name, column_type)
    """
    logger.info(f"🔍 Vérification des colonnes dans la table {table_name}...")

    # Vérifie si la table existe
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        logger.info(f"⚠️  Table {table_name} n'existe pas encore, elle sera créée par SQLAlchemy")
        return

    columns_added = []
    columns_already_exist = []

    with engine.connect() as conn:
        for column_name, column_type in columns_def:
            if not column_exists(table_name, column_name):
                # Ajoute la colonne
                try:
                    sql = text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    conn.execute(sql)
                    conn.commit()
                    columns_added.append(column_name)
                    logger.info(f"  ✅ Colonne ajoutée: {column_name} ({column_type})")
                except Exception as e:
                    logger.error(f"  ❌ Erreur lors de l'ajout de {column_name}: {e}")
            else:
                columns_already_exist.append(column_name)

    # Résumé
    if columns_added:
        logger.info(f"✅ Migration {table_name}: {len(columns_added)} colonnes ajoutées")
    else:
        logger.info(f"✅ Table {table_name}: toutes les colonnes existent déjà ({len(columns_already_exist)} colonnes)")


def add_sirene_columns_if_needed():
    """Ajoute les colonnes Sirene à la table invitations."""
    add_columns_to_table("invitations", SIRENE_COLUMNS)


def add_manual_invitation_columns_if_needed():
    """Ajoute les colonnes pour l'ajout manuel d'invitations PAP."""
    add_columns_to_table("invitations", MANUAL_INVITATION_COLUMNS)


def add_pv_events_columns_if_needed():
    """Ajoute les nouvelles colonnes v1.0.0 à la table pv_events."""
    add_columns_to_table("pv_events", PV_EVENTS_NEW_COLUMNS)


def add_siret_summary_columns_if_needed():
    """Ajoute les nouvelles colonnes v1.0.0 à la table siret_summary."""
    add_columns_to_table("siret_summary", SIRET_SUMMARY_NEW_COLUMNS)


def _normalize_raw_key(key: str) -> str:
    """Normalise une clé de dictionnaire raw pour la recherche."""
    import unicodedata
    import re
    key = unicodedata.normalize("NFKD", str(key))
    key = "".join(ch for ch in key if not unicodedata.combining(ch))
    key = key.lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _pick_from_raw(raw_dict: dict, *keys: str) -> str | None:
    """Récupère la première valeur non-None depuis raw_dict pour les clés données."""
    if not raw_dict:
        return None
    for key in keys:
        norm = _normalize_raw_key(key)
        if norm and norm in raw_dict:
            value = raw_dict[norm]
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _pick_bool_from_raw(raw_dict: dict, *keys: str) -> bool | None:
    """Récupère une valeur booléenne depuis raw_dict."""
    value = _pick_from_raw(raw_dict, *keys)
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"1", "oui", "o", "yes", "y", "true"}:
        return True
    if lowered in {"0", "non", "n", "no", "false"}:
        return False
    return None


def fill_invitation_columns_from_raw():
    """
    Remplit les colonnes structurées des invitations depuis le champ raw.
    Cette migration est utile pour les données importées avant l'ajout du code
    d'extraction automatique dans etl.py.
    """
    logger.info("🔍 Remplissage des colonnes invitations depuis le champ raw...")

    from sqlalchemy.orm import Session
    from .models import Invitation

    session = Session(bind=engine)

    try:
        # Compte d'abord les statistiques
        total_invitations = session.query(Invitation).count()
        invitations_with_raw = session.query(Invitation).filter(Invitation.raw.isnot(None)).count()
        denomination_null = session.query(Invitation).filter(Invitation.denomination.is_(None)).count()

        logger.info(f"  📊 Statistiques :")
        logger.info(f"    • Total invitations        : {total_invitations}")
        logger.info(f"    • Avec champ raw rempli    : {invitations_with_raw}")
        logger.info(f"    • Denomination NULL        : {denomination_null}")

        # Récupère toutes les invitations qui ont un champ raw non-null
        invitations = session.query(Invitation).filter(Invitation.raw.isnot(None)).all()

        if not invitations:
            logger.warning("  ⚠️  Aucune invitation avec données raw à traiter")
            logger.warning("  💡 Si le tableau est vide, les données n'ont peut-être pas de champ raw.")
            logger.warning("  💡 Exécutez le script : python scripts/migrate_and_fix_invitations.py")
            return

        updated_count = 0
        skipped_already_filled = 0

        for inv in invitations:
            raw = inv.raw or {}
            updated = False

            # Si les colonnes importantes sont déjà remplies ET les colonnes manuelles aussi, on skip
            if (inv.denomination and inv.commune and inv.code_postal and
                inv.fd and inv.ud and inv.idcc):
                skipped_already_filled += 1
                continue

            # Denomination
            if not inv.denomination:
                inv.denomination = _pick_from_raw(
                    raw,
                    "denomination", "denomination_usuelle", "raison_sociale", "raison sociale",
                    "raison_sociale_etablissement", "nom_raison_sociale", "rs", "nom",
                    "nom_entreprise", "societe", "entreprise", "nom_de_l_entreprise", "libelle"
                )
                if inv.denomination:
                    updated = True

            # Enseigne
            if not inv.enseigne:
                inv.enseigne = _pick_from_raw(raw, "enseigne", "enseigne_commerciale", "enseigne commerciale", "nom_commercial")
                if inv.enseigne:
                    updated = True

            # Adresse
            if not inv.adresse:
                inv.adresse = _pick_from_raw(
                    raw,
                    "adresse_complete", "adresse", "adresse_ligne_1", "adresse_ligne1", "adresse_ligne 1",
                    "adresse1", "adresse_postale", "ligne_4", "ligne4", "libelle_voie", "libelle_voie_etablissement",
                    "rue", "numero_et_voie", "voie", "adresse_etablissement", "adresse2", "complement_adresse",
                    "numero_voie", "adresse_geo", "adresse_complete_etablissement"
                )
                if inv.adresse:
                    updated = True

            # Code postal
            if not inv.code_postal:
                inv.code_postal = _pick_from_raw(
                    raw, "code_postal", "code postal", "cp", "code_postal_etablissement", "postal"
                )
                if inv.code_postal:
                    updated = True

            # Commune
            if not inv.commune:
                inv.commune = _pick_from_raw(
                    raw, "commune", "ville", "localite", "adresse_ville", "libelle_commune_etablissement", "city"
                )
                if inv.commune:
                    updated = True

            # Activité principale
            if not inv.activite_principale:
                inv.activite_principale = _pick_from_raw(
                    raw, "activite_principale", "code_naf", "naf", "code_ape", "ape"
                )
                if inv.activite_principale:
                    updated = True

            # Libellé activité
            if not inv.libelle_activite:
                inv.libelle_activite = _pick_from_raw(
                    raw, "libelle_activite", "libelle activité", "libelle_naf", "activite",
                    "activite_principale_libelle"
                )
                if inv.libelle_activite:
                    updated = True

            # Tranche effectifs
            if not inv.tranche_effectifs:
                inv.tranche_effectifs = _pick_from_raw(
                    raw, "tranche_effectifs", "tranche_effectif", "tranche_effectifs_salaries",
                    "tranche_effectif_salarie"
                )
                if inv.tranche_effectifs:
                    updated = True

            # Effectifs label
            if not inv.effectifs_label:
                inv.effectifs_label = _pick_from_raw(
                    raw, "effectifs", "effectif", "effectifs_salaries", "effectifs salaries", "effectifs categorie",
                    "effectif_salarie", "nb_salaries", "nombre_salaries", "salaries", "nombre_de_salaries",
                    "effectif_total", "total_effectif", "nb_employes", "nombre_employes"
                )
                if inv.effectifs_label:
                    updated = True

            # Catégorie entreprise
            if not inv.categorie_entreprise:
                inv.categorie_entreprise = _pick_from_raw(
                    raw, "categorie_entreprise", "categorie", "taille_entreprise", "taille"
                )
                if inv.categorie_entreprise:
                    updated = True

            # Est actif
            if inv.est_actif is None:
                inv.est_actif = _pick_bool_from_raw(raw, "est_actif", "actif", "etat_etablissement", "etat")
                if inv.est_actif is not None:
                    updated = True

            # Est siège
            if inv.est_siege is None:
                inv.est_siege = _pick_bool_from_raw(raw, "est_siege", "siege", "siege_social")
                if inv.est_siege is not None:
                    updated = True

            # Colonnes manuelles pour ajout PAP
            if not inv.ud:
                inv.ud = _pick_from_raw(raw, "ud", "union_departementale", "union departementale", "departement", "dep")
                if inv.ud:
                    updated = True

            if not inv.fd:
                inv.fd = _pick_from_raw(raw, "fd", "federation", "fédération")
                if inv.fd:
                    updated = True

            if not inv.idcc:
                inv.idcc = _pick_from_raw(raw, "idcc", "code_idcc", "convention_collective")
                if inv.idcc:
                    updated = True

            if not inv.effectif_connu:
                effectif_str = _pick_from_raw(raw, "effectif_connu", "effectif connu", "effectif_manuel", "effectif manuel")
                if effectif_str:
                    try:
                        inv.effectif_connu = int(float(str(effectif_str).replace(",", ".").strip()))
                        updated = True
<<<<<<< HEAD
                    except (ValueError, TypeError, AttributeError):
=======
                    except:
>>>>>>> claude/fix-electoral-quotient-calculation-011CUrhaod8vzkG7ZHeXooi3
                        pass

            if not inv.structure_saisie:
                inv.structure_saisie = _pick_from_raw(raw, "structure_saisie", "structure saisie", "structure", "organisation")
                if inv.structure_saisie:
                    updated = True

            if updated:
                updated_count += 1

        session.commit()
        logger.info(f"✅ Migration terminée !")
        logger.info(f"    • Invitations mises à jour    : {updated_count}")
        logger.info(f"    • Invitations déjà remplies   : {skipped_already_filled}")
        logger.info(f"    • Total traité                : {updated_count + skipped_already_filled}")

        if updated_count == 0 and denomination_null > 0:
            logger.warning("  ⚠️  Aucune mise à jour effectuée mais des colonnes sont NULL")
            logger.warning("  💡 Les données n'ont probablement pas de champ raw rempli")
            logger.warning("  💡 Exécutez : python scripts/migrate_and_fix_invitations.py")

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur lors du remplissage des colonnes: {e}")
    finally:
        session.close()


def run_migrations():
    """Point d'entrée pour exécuter toutes les migrations."""
    try:
        logger.info("🚀 Démarrage des migrations de base de données...")

        # Migration Sirene pour invitations
        add_sirene_columns_if_needed()

        # Migration colonnes manuelles pour invitations PAP
        add_manual_invitation_columns_if_needed()

        # Migration données invitations
        fill_invitation_columns_from_raw()

        logger.info("✅ Toutes les migrations ont été exécutées avec succès!")
    except Exception as e:
        logger.error(f"❌ Erreur lors des migrations: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Ne pas lever l'exception pour ne pas bloquer le démarrage
        # L'application peut démarrer même si les migrations échouent
