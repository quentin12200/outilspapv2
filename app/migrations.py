# app/migrations.py
"""
Migrations automatiques pour ajouter les colonnes Sirene si elles n'existent pas.
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


def column_exists(table_name: str, column_name: str) -> bool:
    """Vérifie si une colonne existe dans une table."""
    inspector = inspect(engine)

    # Vérifie si la table existe
    if table_name not in inspector.get_table_names():
        return False

    # Récupère les colonnes de la table
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_sirene_columns_if_needed():
    """
    Ajoute les colonnes Sirene à la table invitations si elles n'existent pas.
    Cette migration est idempotente (peut être exécutée plusieurs fois sans problème).
    """
    logger.info("🔍 Vérification des colonnes Sirene dans la table invitations...")

    # Vérifie si la table invitations existe
    inspector = inspect(engine)
    if "invitations" not in inspector.get_table_names():
        logger.info("⚠️  Table invitations n'existe pas encore, elle sera créée par SQLAlchemy")
        return

    columns_added = []
    columns_already_exist = []

    with engine.connect() as conn:
        for column_name, column_type in SIRENE_COLUMNS:
            if not column_exists("invitations", column_name):
                # Ajoute la colonne
                try:
                    sql = text(f"ALTER TABLE invitations ADD COLUMN {column_name} {column_type}")
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
        logger.info(f"✅ Migration terminée: {len(columns_added)} colonnes Sirene ajoutées")
    else:
        logger.info(f"✅ Toutes les colonnes Sirene existent déjà ({len(columns_already_exist)}/13)")


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

            # Si les colonnes importantes sont déjà remplies, on skip
            if inv.denomination and inv.commune and inv.code_postal:
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
        add_sirene_columns_if_needed()
        fill_invitation_columns_from_raw()
    except Exception as e:
        logger.error(f"❌ Erreur lors des migrations: {e}")
        # Ne pas lever l'exception pour ne pas bloquer le démarrage
        # L'application peut démarrer même si les migrations échouent
