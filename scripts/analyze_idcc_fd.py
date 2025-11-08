#!/usr/bin/env python3
"""
Script pour analyser les invitations avec IDCC mais sans FD.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import Invitation, PVEvent
from sqlalchemy import func

def analyze():
    session = SessionLocal()

    try:
        print("=" * 80)
        print("ANALYSE DES CORRESPONDANCES IDCC-FD")
        print("=" * 80)
        print()

        # Statistiques sur les invitations
        total_invitations = session.query(func.count(Invitation.id)).scalar() or 0
        print(f"Total invitations: {total_invitations}")

        if total_invitations == 0:
            print("\n⚠️  Aucune invitation trouvée dans la base")
            print("   Importez d'abord les invitations avant de continuer.")
            return

        # Invitations avec IDCC
        with_idcc = session.query(func.count(Invitation.id)).filter(
            Invitation.idcc.isnot(None),
            Invitation.idcc != ""
        ).scalar() or 0
        print(f"Invitations avec IDCC: {with_idcc}")

        # Invitations avec FD
        with_fd = session.query(func.count(Invitation.id)).filter(
            Invitation.fd.isnot(None),
            Invitation.fd != ""
        ).scalar() or 0
        print(f"Invitations avec FD: {with_fd}")

        # Invitations avec IDCC mais sans FD (problème!)
        idcc_no_fd = session.query(func.count(Invitation.id)).filter(
            Invitation.idcc.isnot(None),
            Invitation.idcc != "",
            (Invitation.fd.is_(None) | (Invitation.fd == ""))
        ).scalar() or 0
        print(f"\n❌ Invitations avec IDCC mais SANS FD: {idcc_no_fd}")

        if idcc_no_fd > 0:
            print(f"   ⚠️  Ces {idcc_no_fd} entreprises DOIVENT avoir une FD !")
            print()

            # Afficher quelques exemples
            print("Exemples d'invitations avec IDCC mais sans FD:")
            examples = session.query(Invitation).filter(
                Invitation.idcc.isnot(None),
                Invitation.idcc != "",
                (Invitation.fd.is_(None) | (Invitation.fd == ""))
            ).limit(10).all()

            for inv in examples:
                print(f"  • SIRET: {inv.siret}")
                print(f"    IDCC: {inv.idcc}")
                print(f"    FD: {repr(inv.fd)}")
                print(f"    Dénomination: {inv.denomination or 'N/A'}")
                print()

        print("=" * 80)
        print("ANALYSE DE LA BASE PV")
        print("=" * 80)
        print()

        # Statistiques sur les PV
        total_pv = session.query(func.count(PVEvent.id)).scalar() or 0
        print(f"Total PV: {total_pv}")

        if total_pv == 0:
            print("\n⚠️  Aucun PV trouvé dans la base")
            print("   La table Tous_PV est vide.")
            print("   Vous devez télécharger la base de données complète.")
            return

        # PV avec IDCC et FD
        pv_with_both = session.query(func.count(PVEvent.id)).filter(
            PVEvent.idcc.isnot(None),
            PVEvent.idcc != "",
            PVEvent.fd.isnot(None),
            PVEvent.fd != ""
        ).scalar() or 0
        print(f"PV avec IDCC et FD: {pv_with_both}")

        # Compter les correspondances IDCC → FD uniques
        idcc_fd_pairs = session.query(
            PVEvent.idcc,
            PVEvent.fd,
            func.count().label('count')
        ).filter(
            PVEvent.idcc.isnot(None),
            PVEvent.idcc != "",
            PVEvent.fd.isnot(None),
            PVEvent.fd != ""
        ).group_by(PVEvent.idcc, PVEvent.fd).all()

        if idcc_fd_pairs:
            print(f"\nCorrespondances IDCC → FD trouvées: {len(idcc_fd_pairs)}")
            print("\nExemples de correspondances (10 premiers):")
            for idcc, fd, count in idcc_fd_pairs[:10]:
                print(f"  IDCC {idcc:6} → {fd:30} ({count} PV)")
        else:
            print("\n❌ Aucune correspondance IDCC → FD trouvée dans les PV")

    finally:
        session.close()

if __name__ == "__main__":
    analyze()
