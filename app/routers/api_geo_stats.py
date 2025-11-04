"""
API pour les statistiques géographiques (carte de France)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, List, Any
from ..db import get_session
from ..models import PVEvent

router = APIRouter(
    prefix="/api/geo",
    tags=["geo-stats"]
)


@router.get("/departements/inscrits")
def get_departements_inscrits_stats(db: Session = Depends(get_session)):
    """
    Retourne les statistiques d'inscrits par département :
    - Total des inscrits par département
    - Nombre de cibles avec 1000+ inscrits
    - Liste des établissements avec 1000+ inscrits par département
    """

    # Récupérer tous les PV avec leurs inscrits
    query = db.query(
        PVEvent.cp,
        PVEvent.siret,
        PVEvent.raison_sociale,
        PVEvent.inscrits,
        PVEvent.ville,
        PVEvent.cycle
    ).filter(
        PVEvent.cp.isnot(None),
        PVEvent.inscrits.isnot(None),
        PVEvent.inscrits > 0
    ).all()

    # Dictionnaire pour stocker les stats par département
    dept_stats = {}

    for row in query:
        if not row.cp or len(row.cp) < 2:
            continue

        # Extraire le département (2 premiers chiffres du code postal)
        dept = row.cp[:2]

        # Cas spéciaux : Corse et DOM-TOM
        if dept in ['20', '2A', '2B']:
            if len(row.cp) >= 3:
                if row.cp[2] in ['A', 'a']:
                    dept = '2A'
                elif row.cp[2] in ['B', 'b']:
                    dept = '2B'
                else:
                    dept = '20'

        # Initialiser le département si nécessaire
        if dept not in dept_stats:
            dept_stats[dept] = {
                'dept': dept,
                'total_inscrits': 0,
                'nb_cibles_1000plus': 0,
                'cibles_1000plus': []
            }

        # Ajouter au total des inscrits
        inscrits_val = float(row.inscrits) if row.inscrits else 0
        dept_stats[dept]['total_inscrits'] += inscrits_val

        # Si 1000+ inscrits, ajouter aux cibles importantes
        if inscrits_val >= 1000:
            # Vérifier si ce SIRET n'est pas déjà dans la liste
            siret_exists = any(
                c['siret'] == row.siret
                for c in dept_stats[dept]['cibles_1000plus']
            )

            if not siret_exists:
                dept_stats[dept]['nb_cibles_1000plus'] += 1
                dept_stats[dept]['cibles_1000plus'].append({
                    'siret': row.siret,
                    'raison_sociale': row.raison_sociale or 'N/C',
                    'inscrits': int(inscrits_val),
                    'ville': row.ville or 'N/C',
                    'cycle': row.cycle
                })

    # Trier les cibles par nombre d'inscrits décroissant
    for dept in dept_stats.values():
        dept['cibles_1000plus'].sort(key=lambda x: x['inscrits'], reverse=True)
        dept['total_inscrits'] = int(dept['total_inscrits'])

    # Convertir en liste et trier par département
    result = list(dept_stats.values())
    result.sort(key=lambda x: x['dept'])

    return {
        'departements': result,
        'total_cibles_1000plus': sum(d['nb_cibles_1000plus'] for d in result),
        'total_inscrits_france': sum(d['total_inscrits'] for d in result)
    }


@router.get("/departements/top-cibles")
def get_top_cibles(
    min_inscrits: int = 1000,
    limit: int = 100,
    db: Session = Depends(get_session)
):
    """
    Retourne la liste des plus grosses cibles (établissements avec le plus d'inscrits)
    """

    # Grouper par SIRET pour éviter les doublons (un SIRET peut avoir plusieurs PV)
    # On prend le max des inscrits pour chaque SIRET
    subquery = db.query(
        PVEvent.siret,
        func.max(PVEvent.inscrits).label('max_inscrits')
    ).filter(
        PVEvent.siret.isnot(None),
        PVEvent.inscrits.isnot(None),
        PVEvent.inscrits >= min_inscrits
    ).group_by(PVEvent.siret).subquery()

    # Récupérer les infos complètes pour ces SIRETs
    query = db.query(
        PVEvent.siret,
        PVEvent.raison_sociale,
        PVEvent.inscrits,
        PVEvent.cp,
        PVEvent.ville,
        PVEvent.cycle,
        PVEvent.ud,
        PVEvent.fd
    ).join(
        subquery,
        and_(
            PVEvent.siret == subquery.c.siret,
            PVEvent.inscrits == subquery.c.max_inscrits
        )
    ).order_by(
        PVEvent.inscrits.desc()
    ).limit(limit).all()

    result = []
    for row in query:
        dept = row.cp[:2] if row.cp and len(row.cp) >= 2 else 'N/C'
        result.append({
            'siret': row.siret,
            'raison_sociale': row.raison_sociale or 'N/C',
            'inscrits': int(row.inscrits) if row.inscrits else 0,
            'departement': dept,
            'ville': row.ville or 'N/C',
            'cycle': row.cycle,
            'ud': row.ud,
            'fd': row.fd
        })

    return {
        'cibles': result,
        'total': len(result),
        'min_inscrits': min_inscrits
    }
