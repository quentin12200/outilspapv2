#!/usr/bin/env python3
"""
Migration pour créer les tables du système de tableau de bord UD

Usage:
    python create_ud_tables.py

Ce script crée les 4 nouvelles tables :
- tableaux_bord_ud
- entreprises_ud
- evenements_ud
- elections_ud
"""

import logging
from sqlalchemy import text
from app.db import engine, Base
from app.models import TableauBordUD, EntrepriseUD, EvenementUD, ElectionUD

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_table_exists(table_name: str) -> bool:
    """Vérifie si une table existe déjà"""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"
        ), {"table_name": table_name})
        return result.fetchone() is not None


def create_ud_tables():
    """Crée les tables pour le système de tableau de bord UD"""

    tables_to_create = [
        ("tableaux_bord_ud", TableauBordUD),
        ("entreprises_ud", EntrepriseUD),
        ("evenements_ud", EvenementUD),
        ("elections_ud", ElectionUD)
    ]

    logger.info("=== Migration : Création des tables UD ===")

    for table_name, model_class in tables_to_create:
        if check_table_exists(table_name):
            logger.info(f"✓ Table '{table_name}' existe déjà - ignorée")
        else:
            try:
                logger.info(f"→ Création de la table '{table_name}'...")
                model_class.__table__.create(bind=engine, checkfirst=True)
                logger.info(f"✓ Table '{table_name}' créée avec succès")
            except Exception as e:
                logger.error(f"✗ Erreur lors de la création de '{table_name}': {e}")
                raise

    logger.info("=== Migration terminée avec succès ===")


def add_sample_data():
    """Ajoute des données de test pour un tableau UD exemple"""
    from datetime import datetime, date, timedelta
    from app.db import SessionLocal

    logger.info("\n=== Ajout de données de test ===")

    session = SessionLocal()

    try:
        # Vérifier si des données existent déjà
        existing = session.query(TableauBordUD).filter_by(code_ud="udtest").first()
        if existing:
            logger.info("✓ Données de test déjà présentes - ignorées")
            return

        # 1. Créer un tableau de bord UD de test
        logger.info("→ Création du tableau de bord UD Test...")
        tableau_ud = TableauBordUD(
            numero_departement="99",
            nom_departement="Test",
            code_ud="udtest",
            email_ud="udtest@cgt.fr",
            telephone_ud="01 23 45 67 89",
            created_at=datetime.now()
        )
        session.add(tableau_ud)
        session.flush()  # Pour obtenir l'ID

        logger.info(f"✓ Tableau UD Test créé (ID: {tableau_ud.id})")

        # 2. Ajouter des entreprises cibles (CGT présente)
        logger.info("→ Ajout d'entreprises cibles...")

        entreprise1 = EntrepriseUD(
            tableau_bord_id=tableau_ud.id,
            siret="12345678901234",
            nom_entreprise="Entreprise Exemple SA",
            enseigne="Exemple Industries",
            type_cible="presente",
            nb_salaries=250,
            tranche_effectifs="250-499",
            code_postal="75001",
            ville="Paris",
            adresse="123 Rue de l'Exemple, 75001 Paris",
            idcc="1234",
            deno_coll="Métallurgie",
            nb_syndiques=25,
            date_derniere_election=date(2023, 3, 15),
            date_prochaine_election=date(2027, 3, 15),
            voix_cgt=120,
            taux_participation=85.5,
            pilote="Jean Dupont",
            objet="Développer la section syndicale",
            enjeux="Renouvellement CE - maintenir notre présence",
            nom_contact="Marie Martin",
            telephone_contact="01 23 45 67 90",
            email_contact="marie.martin@exemple.fr",
            organisation_resp="UL Paris Centre",
            created_at=datetime.now()
        )
        session.add(entreprise1)

        entreprise2 = EntrepriseUD(
            tableau_bord_id=tableau_ud.id,
            siret="98765432109876",
            nom_entreprise="TechCorp France",
            type_cible="presente",
            nb_salaries=120,
            tranche_effectifs="100-249",
            code_postal="75015",
            ville="Paris",
            nb_syndiques=15,
            date_derniere_election=date(2022, 6, 10),
            date_prochaine_election=date(2026, 6, 10),
            voix_cgt=45,
            pilote="Sophie Leroy",
            objet="Renforcer la syndicalisation",
            enjeux="Entreprise en croissance - recruter de nouveaux adhérents",
            created_at=datetime.now()
        )
        session.add(entreprise2)

        # 3. Ajouter des entreprises absentes (CGT non présente)
        logger.info("→ Ajout d'entreprises cibles absentes...")

        entreprise3 = EntrepriseUD(
            tableau_bord_id=tableau_ud.id,
            siret="11111111111111",
            nom_entreprise="NouvelleBoîte SAS",
            type_cible="absente",
            nb_salaries=180,
            tranche_effectifs="100-249",
            code_postal="75012",
            ville="Paris",
            date_prochaine_election=date.today() + timedelta(days=120),
            pilote="Marc Dubois",
            objet="Implanter la CGT",
            enjeux="Première élection CSE - aucun syndicat présent actuellement",
            created_at=datetime.now()
        )
        session.add(entreprise3)

        session.flush()  # Pour obtenir les IDs des entreprises

        logger.info(f"✓ {3} entreprises ajoutées")

        # 4. Ajouter des élections pour les entreprises
        logger.info("→ Ajout d'élections...")

        election1 = ElectionUD(
            entreprise_id=entreprise1.id,
            date_scrutin=date(2023, 3, 15),
            type_election="CSE",
            duree_mandat=4.0,
            nb_inscrits=200,
            nb_votants=171,
            nb_suffrages_exprimes=165,
            taux_participation=85.5,
            voix_cgt=120,
            siege_cgt=3,
            pct_cgt=72.7,
            voix_cfdt=30,
            voix_fo=15,
            siege_cfdt=1,
            siege_fo=0,
            nb_colleges=2,
            date_prochain_scrutin=date(2027, 3, 15),
            observations="Excellents résultats CGT - maintien de la majorité",
            created_at=datetime.now()
        )
        session.add(election1)

        election2 = ElectionUD(
            entreprise_id=entreprise2.id,
            date_scrutin=date(2022, 6, 10),
            type_election="CSE",
            duree_mandat=4.0,
            nb_inscrits=95,
            nb_votants=78,
            nb_suffrages_exprimes=75,
            taux_participation=82.1,
            voix_cgt=45,
            siege_cgt=2,
            pct_cgt=60.0,
            voix_cfdt=20,
            voix_unsa=10,
            siege_cfdt=1,
            nb_colleges=1,
            date_prochain_scrutin=date(2026, 6, 10),
            created_at=datetime.now()
        )
        session.add(election2)

        logger.info(f"✓ {2} élections ajoutées")

        # 5. Ajouter des événements/réunions
        logger.info("→ Ajout d'événements...")

        evenement1 = EvenementUD(
            tableau_bord_id=tableau_ud.id,
            titre="Réunion mensuelle UD",
            date_heure=datetime.now() + timedelta(days=7, hours=14),
            rubrique="Réunion",
            presentateur="Secrétaire UD",
            ordre_du_jour="Bilan du mois, préparation campagnes électorales",
            lieu="Bourse du Travail",
            statut="prevu",
            created_at=datetime.now()
        )
        session.add(evenement1)

        evenement2 = EvenementUD(
            tableau_bord_id=tableau_ud.id,
            entreprise_id=entreprise1.id,
            titre="Formation délégués CSE - Entreprise Exemple",
            date_heure=datetime.now() + timedelta(days=14, hours=9),
            rubrique="Formation",
            presentateur="Formateur CGT",
            referent_cec="Jean Dupont",
            ordre_du_jour="Formation des nouveaux élus CSE",
            lieu="Siège de l'entreprise",
            statut="prevu",
            created_at=datetime.now()
        )
        session.add(evenement2)

        evenement3 = EvenementUD(
            tableau_bord_id=tableau_ud.id,
            entreprise_id=entreprise3.id,
            titre="Campagne de tractage - NouvelleBoîte",
            date_heure=datetime.now() + timedelta(days=3, hours=7, minutes=30),
            rubrique="Action",
            presentateur="Marc Dubois",
            ordre_du_jour="Distribution de tracts d'information sur les élections CSE",
            lieu="Devant l'entreprise",
            statut="prevu",
            created_at=datetime.now()
        )
        session.add(evenement3)

        logger.info(f"✓ {3} événements ajoutés")

        # 6. Mettre à jour les statistiques du tableau UD
        tableau_ud.nb_entreprises_cibles = 2
        tableau_ud.nb_entreprises_absentes = 1
        tableau_ud.nb_total_syndiques = 40
        tableau_ud.nb_prochaines_elections = 1

        # Commit final
        session.commit()
        logger.info("✓ Toutes les données de test ont été ajoutées avec succès")
        logger.info(f"\n📊 Tableau de bord UD Test créé :")
        logger.info(f"   - Code UD: {tableau_ud.code_ud}")
        logger.info(f"   - Département: {tableau_ud.nom_departement} ({tableau_ud.numero_departement})")
        logger.info(f"   - Entreprises cibles (CGT présente): {tableau_ud.nb_entreprises_cibles}")
        logger.info(f"   - Entreprises absentes (implantation): {tableau_ud.nb_entreprises_absentes}")
        logger.info(f"   - Total syndiqués: {tableau_ud.nb_total_syndiques}")
        logger.info(f"   - Événements planifiés: 3")

    except Exception as e:
        session.rollback()
        logger.error(f"✗ Erreur lors de l'ajout des données de test: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    try:
        # Créer les tables
        create_ud_tables()

        # Ajouter des données de test
        add_sample_data()

        print("\n✅ Migration terminée avec succès !")
        print("\n📌 Prochaines étapes :")
        print("   1. Créer les routes API pour gérer les tableaux UD")
        print("   2. Créer les templates HTML pour l'interface")
        print("   3. Tester l'affichage du tableau UD Test")

    except Exception as e:
        logger.error(f"\n❌ Erreur fatale: {e}")
        exit(1)
