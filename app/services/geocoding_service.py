"""
Service de géocodage utilisant l'API Pappers
"""
import logging
import asyncio
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import PVEvent, Invitation
from app.services.pappers_api import pappers_api

logger = logging.getLogger(__name__)

async def geocode_batch(db: Session, limit: int = 50):
    """
    Géocode un lot d'établissements (PVEvent et Invitation) qui n'ont pas de coordonnées.
    Priorité aux établissements avec le plus d'inscrits (PVEvent).
    """
    if not pappers_api.api_key:
        logger.warning("Clé API Pappers non configurée, géocodage impossible.")
        return 0

    count = 0
    
    # 1. Géocoder les PVEvent (prioritaires)
    # On prend ceux qui n'ont pas de lat/lon et qui ont un SIRET valide
    pvs = db.query(PVEvent).filter(
        PVEvent.latitude.is_(None),
        PVEvent.siret.isnot(None),
        PVEvent.siret != ""
    ).order_by(PVEvent.inscrits.desc()).limit(limit).all()

    for pv in pvs:
        try:
            # On utilise get_siret pour avoir les infos précises dont la géoloc
            info = await pappers_api.get_siret(pv.siret)
            if info and info.get("latitude") and info.get("longitude"):
                pv.latitude = info["latitude"]
                pv.longitude = info["longitude"]
                count += 1
                logger.info(f"Géocodé PV {pv.siret}: {pv.latitude}, {pv.longitude}")
            else:
                # Marquer comme traité mais sans résultat (pour éviter de re-boucler indéfiniment)
                # On pourrait mettre 0.0 ou une valeur témoin, ou juste logger
                # Ici on laisse NULL pour retenter plus tard ou via un autre service
                logger.debug(f"Pas de géoloc pour PV {pv.siret}")
            
            # Petit délai pour rate limit si besoin (Pappers est assez large mais bon)
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Erreur géocodage PV {pv.siret}: {e}")

    # Commit intermédiaire
    db.commit()
    
    if count >= limit:
        return count

    # 2. Géocoder les Invitations (si quota restant)
    remaining = limit - count
    invitations = db.query(Invitation).filter(
        Invitation.latitude.is_(None),
        Invitation.siret.isnot(None)
    ).limit(remaining).all()

    for inv in invitations:
        try:
            info = await pappers_api.get_siret(inv.siret)
            if info and info.get("latitude") and info.get("longitude"):
                inv.latitude = info["latitude"]
                inv.longitude = info["longitude"]
                count += 1
                logger.info(f"Géocodé Invitation {inv.siret}: {inv.latitude}, {inv.longitude}")
            
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Erreur géocodage Invitation {inv.siret}: {e}")

    db.commit()
    return count
