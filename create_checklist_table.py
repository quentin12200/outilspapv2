"""
Script de migration pour créer la table checklist_items_ud
et pré-remplir les items méthodologiques pour les entreprises CGT absente
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer app
sys.path.append(str(Path(__file__).parent))

from app.db import engine, Base
from app.models import ChecklistItemUD, EntrepriseUD
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Items de checklist par défaut pour CGT PRÉSENTE (renforcement / développement)
CHECKLIST_RENFORCEMENT = [
    # Si l'UD apporte la connaissance
    {
        "categorie": "ud_connaissance",
        "libelle": "de la situation géographique et du secteur professionnel de la cible (filière client, fournisseur etc.) et de syndicats à proximité",
        "ordre": 1
    },
    {
        "categorie": "ud_connaissance",
        "libelle": "d'une ancienne présence CGT",
        "ordre": 2
    },
    {
        "categorie": "ud_connaissance",
        "libelle": "de syndiqués individuels issus de la cible COGITIEL UL ou INTERNET ou rattachés à un syndicat en proximité",
        "ordre": 3
    },
    {
        "categorie": "ud_connaissance",
        "libelle": "de SALARIÉS accueillis en permanence juridique",
        "ordre": 4
    },
    {
        "categorie": "ud_connaissance",
        "libelle": "de CONTACTS de salariés dans la proximité amicale, familiale, associative ou même professionnelle de nos syndiqués (Appel des syndicats)",
        "ordre": 5
    },

    # Mise à disposition des contenus liés à la connaissance (UD)
    {
        "categorie": "mise_dispo_ud",
        "libelle": "des réalités locales (transports, restaurations, garde d'enfants...)",
        "ordre": 1
    },
    {
        "categorie": "mise_dispo_ud",
        "libelle": "à l'actualité revendicative au plan interprofessionnel, aux conquêtes et résultats électoraux significatifs dans les entreprises « phares » du territoire,",
        "ordre": 2
    },
    {
        "categorie": "mise_dispo_ud",
        "libelle": "au poids et à l'histoire de la CGT sur le territoire et CFD",
        "ordre": 3
    },

    # Si FD apporte la connaissance
    {
        "categorie": "fd_connaissance",
        "libelle": "d'un syndiqué individuel de la cible rattaché à un syndicat du champ fédéral",
        "ordre": 1
    },
    {
        "categorie": "fd_connaissance",
        "libelle": "d'une cible constitutive d'un groupe (ex KEOUIS/SNCF), présence d'un DSC et de syndicats",
        "ordre": 2
    },
    {
        "categorie": "fd_connaissance",
        "libelle": "de la présence d'un syndicat CGT et d'un DSC en proximité dans le même secteur pro ou champ (donneur d'ordre, sous-traitant, client, fournisseur etc...): permettant au-delà d'un parrainage d'un syndicat, une démarche de syndicats en réseau.",
        "ordre": 3
    },
    {
        "categorie": "fd_connaissance",
        "libelle": "de la filière professionnelle de la cible dans d'autres secteurs (client, fournisseur etc.. ex : ambulances hopital.)",
        "ordre": 4
    },

    # Mise à disposition des contenus liés à la connaissance (FD)
    {
        "categorie": "mise_dispo_fd",
        "libelle": "des besoins identifiés et réalités des salariés du secteur (salaires, précarité, conditions de travail, femmes, ICT, horaires, pénibilité etc.)",
        "ordre": 1
    },
    {
        "categorie": "mise_dispo_fd",
        "libelle": "de l'actualitée revendicative et des enjeux au niveau de la branche ou de la filière, de conquêtes et résultats électoraux significatifs dans les entreprises.",
        "ordre": 2
    },
    {
        "categorie": "mise_dispo_fd",
        "libelle": "de situation comparatives avec des entreprises organisées dans le secteur, conquêtes et résultats électoraux significatifs dans les entreprises.",
        "ordre": 3
    },
    {
        "categorie": "mise_dispo_fd",
        "libelle": "calendrier électoral et institutionnel (NAO et échéances diverses ...)",
        "ordre": 4
    },
    {
        "categorie": "mise_dispo_fd",
        "libelle": "au poids et à l'histoire de la CGT dans le groupe, la branche, la filière",
        "ordre": 5
    },

    # Spécifique UGICT UFICT apporte la connaissance
    {
        "categorie": "ugict_connaissance",
        "libelle": "de la présence d'un syndicat CGT organisé dans le territoire et/ou le secteur professionnel autour des collèges 2 et 3",
        "ordre": 1
    },

    # Mise à disposition des contenus liés à la connaissance (UGICT)
    {
        "categorie": "mise_dispo_ugict",
        "libelle": "des besoins, des réalités professionnelles et des enjeux revendicatifs spécifique des salariés des coll. 2 et 3",
        "ordre": 1
    },
    {
        "categorie": "mise_dispo_ugict",
        "libelle": "des conquêtes sociales, de l'actualité électorale syndicale et résultats électoraux significatifs gagnes par la CGT sur les coll. 2 et 3",
        "ordre": 2
    },
    {
        "categorie": "mise_dispo_ugict",
        "libelle": "au poids de la CGT au CFD collège cadre",
        "ordre": 3
    },

    # Parrain
    {
        "categorie": "parrain",
        "libelle": "Terrain",
        "ordre": 1
    },
    {
        "categorie": "parrain",
        "libelle": "Si un ou des syndicats en proximité géographique et/ou professionnelle (filière, groupe, donneur d'ordre, sous-traitant, client, fournisseur etc...): permettant au-delà d'un parrainage d'un syndicat, Une démarche qui articule une consultation avec appel recommande parrain",
        "ordre": 2
    },
]


# Items de checklist par défaut pour CGT ABSENTE (implantation)
CHECKLIST_IMPLANTATION = [
    # Diagnostic initial
    {
        "categorie": "diagnostic",
        "libelle": "Identifier les contacts potentiels (salariés, anciens syndiqués, réseau amical/familial)",
        "ordre": 1
    },
    {
        "categorie": "diagnostic",
        "libelle": "Analyser le secteur d'activité et la situation de l'entreprise",
        "ordre": 2
    },
    {
        "categorie": "diagnostic",
        "libelle": "Cartographier les entreprises du même secteur déjà organisées CGT",
        "ordre": 3
    },

    # Premier contact
    {
        "categorie": "premier_contact",
        "libelle": "Établir un premier contact avec des salariés de l'entreprise",
        "ordre": 1
    },
    {
        "categorie": "premier_contact",
        "libelle": "Identifier les problématiques et revendications des salariés",
        "ordre": 2
    },
    {
        "categorie": "premier_contact",
        "libelle": "Présenter la CGT et ses actions locales",
        "ordre": 3
    },

    # Développement
    {
        "categorie": "developpement",
        "libelle": "Organiser des réunions avec les salariés intéressés",
        "ordre": 1
    },
    {
        "categorie": "developpement",
        "libelle": "Former les futurs délégués et syndiqués",
        "ordre": 2
    },
    {
        "categorie": "developpement",
        "libelle": "Préparer les premières actions revendicatives",
        "ordre": 3
    },

    # Structuration
    {
        "categorie": "structuration",
        "libelle": "Créer la section syndicale CGT",
        "ordre": 1
    },
    {
        "categorie": "structuration",
        "libelle": "Désigner les représentants et délégués",
        "ordre": 2
    },
    {
        "categorie": "structuration",
        "libelle": "Préparer les élections professionnelles",
        "ordre": 3
    },
]


def create_checklist_table():
    """Crée la table checklist_items_ud si elle n'existe pas"""
    inspector = inspect(engine)

    if "checklist_items_ud" in inspector.get_table_names():
        print("✓ Table 'checklist_items_ud' existe déjà")
        return False

    print("Création de la table 'checklist_items_ud'...")
    ChecklistItemUD.__table__.create(engine)
    print("✓ Table 'checklist_items_ud' créée avec succès")
    return True


def initialize_checklist_for_entreprise(db: SessionLocal, entreprise_id: int, type_cible: str):
    """Initialise la checklist pour une entreprise selon son type (presente=renforcement, absente=implantation)"""
    # Choisir le bon template de checklist selon le type
    template = CHECKLIST_RENFORCEMENT if type_cible == "presente" else CHECKLIST_IMPLANTATION

    for item_template in template:
        checklist_item = ChecklistItemUD(
            entreprise_id=entreprise_id,
            categorie=item_template["categorie"],
            libelle=item_template["libelle"],
            ordre=item_template["ordre"],
            est_coche=False,
            informations=""
        )
        db.add(checklist_item)

    db.commit()


def populate_checklists():
    """Crée les checklists pour toutes les entreprises (présente=renforcement, absente=implantation)"""
    db = SessionLocal()

    try:
        # Récupérer TOUTES les entreprises qui n'ont pas encore de checklist
        toutes_entreprises = db.query(EntrepriseUD).all()

        count_renforcement = 0
        count_implantation = 0

        for entreprise in toutes_entreprises:
            # Vérifier si cette entreprise a déjà une checklist
            existing = db.query(ChecklistItemUD).filter(
                ChecklistItemUD.entreprise_id == entreprise.id
            ).first()

            if not existing:
                type_label = "RENFORCEMENT" if entreprise.type_cible == "presente" else "IMPLANTATION"
                print(f"Création checklist {type_label} pour ID {entreprise.id} - {entreprise.nom_entreprise}")
                initialize_checklist_for_entreprise(db, entreprise.id, entreprise.type_cible)

                if entreprise.type_cible == "presente":
                    count_renforcement += 1
                else:
                    count_implantation += 1

        if count_renforcement + count_implantation > 0:
            print(f"✓ {count_renforcement} checklist(s) RENFORCEMENT créée(s)")
            print(f"✓ {count_implantation} checklist(s) IMPLANTATION créée(s)")
        else:
            print("✓ Toutes les entreprises ont déjà leur checklist")

    except Exception as e:
        print(f"❌ Erreur lors de la création des checklists: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("\n=== Migration: Création de la table checklist_items_ud ===\n")

    # Créer la table
    table_created = create_checklist_table()

    # Peupler les checklists pour les entreprises existantes
    if table_created:
        print("\nInitialisation des checklists pour toutes les entreprises...")
        print("  - CGT présente → Checklist RENFORCEMENT")
        print("  - CGT absente → Checklist IMPLANTATION\n")
        populate_checklists()

    print("\n=== Migration terminée ===\n")
