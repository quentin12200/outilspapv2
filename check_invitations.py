#!/usr/bin/env python3
"""Script pour vérifier l'état des invitations et leur IDCC"""

from app.db import SessionLocal
from app.models import Invitation

session = SessionLocal()

# Compter les invitations totales
total = session.query(Invitation).count()

# Compter les invitations sans IDCC
sans_idcc = session.query(Invitation).filter(
    (Invitation.idcc.is_(None)) | (Invitation.idcc == '')
).count()

# Compter les invitations avec IDCC
avec_idcc = session.query(Invitation).filter(
    Invitation.idcc.isnot(None), Invitation.idcc != ''
).count()

# Voir quelques exemples d'invitations sans IDCC
invitations_sans_idcc = session.query(Invitation).filter(
    (Invitation.idcc.is_(None)) | (Invitation.idcc == '')
).limit(5).all()

print(f'Total invitations: {total}')
print(f'Invitations sans IDCC: {sans_idcc}')
print(f'Invitations avec IDCC: {avec_idcc}')
print(f'\nExemples d\'invitations sans IDCC:')
for inv in invitations_sans_idcc:
    print(f'  - SIRET: {inv.siret}, Date enrichissement: {inv.date_enrichissement}')

# Vérifier s'il y a des invitations avec date_enrichissement mais sans IDCC
enrichis_sans_idcc = session.query(Invitation).filter(
    Invitation.date_enrichissement.isnot(None),
    (Invitation.idcc.is_(None)) | (Invitation.idcc == '')
).count()

print(f'\n⚠️ Invitations enrichies mais sans IDCC: {enrichis_sans_idcc}')

session.close()
