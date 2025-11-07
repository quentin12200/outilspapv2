#!/usr/bin/env python3
"""
Script de migration pour nettoyer les valeurs 'nan' dans les tables.
Convertit les chaînes 'nan', 'NaN', 'NAN' en NULL pour les colonnes FD, UD et IDCC.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Invitation, PVEvent, SiretSummary
from sqlalchemy import update

def clean_nan_values():
    """Nettoie les valeurs 'nan' dans toutes les tables."""
    db = SessionLocal()

    try:
        print("🔍 Nettoyage des valeurs 'nan' dans la base de données...")
        print("=" * 70)

        # 1. Nettoyer la table Invitation
        print("\n📋 Table: Invitation")
        print("-" * 70)

        # Compter d'abord
        inv_fd_count = db.query(Invitation).filter(
            Invitation.fd.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        inv_ud_count = db.query(Invitation).filter(
            Invitation.ud.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        inv_idcc_count = db.query(Invitation).filter(
            Invitation.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()

        print(f"  • FD avec 'nan': {inv_fd_count}")
        print(f"  • UD avec 'nan': {inv_ud_count}")
        print(f"  • IDCC avec 'nan': {inv_idcc_count}")

        # Nettoyer FD
        if inv_fd_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.fd.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd=None)
            )
            print(f"  ✅ {inv_fd_count} valeurs FD nettoyées")

        # Nettoyer UD
        if inv_ud_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.ud.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud=None)
            )
            print(f"  ✅ {inv_ud_count} valeurs UD nettoyées")

        # Nettoyer IDCC
        if inv_idcc_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )
            print(f"  ✅ {inv_idcc_count} valeurs IDCC nettoyées")

        # 2. Nettoyer la table PVEvent
        print("\n📋 Table: PVEvent")
        print("-" * 70)

        pv_fd_count = db.query(PVEvent).filter(
            PVEvent.fd.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        pv_ud_count = db.query(PVEvent).filter(
            PVEvent.ud.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        pv_idcc_count = db.query(PVEvent).filter(
            PVEvent.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()

        print(f"  • FD avec 'nan': {pv_fd_count}")
        print(f"  • UD avec 'nan': {pv_ud_count}")
        print(f"  • IDCC avec 'nan': {pv_idcc_count}")

        # Nettoyer FD
        if pv_fd_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.fd.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd=None)
            )
            print(f"  ✅ {pv_fd_count} valeurs FD nettoyées")

        # Nettoyer UD
        if pv_ud_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.ud.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud=None)
            )
            print(f"  ✅ {pv_ud_count} valeurs UD nettoyées")

        # Nettoyer IDCC
        if pv_idcc_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )
            print(f"  ✅ {pv_idcc_count} valeurs IDCC nettoyées")

        # 3. Nettoyer la table SiretSummary
        print("\n📋 Table: SiretSummary")
        print("-" * 70)

        summary_fd_c3_count = db.query(SiretSummary).filter(
            SiretSummary.fd_c3.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_fd_c4_count = db.query(SiretSummary).filter(
            SiretSummary.fd_c4.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_ud_c3_count = db.query(SiretSummary).filter(
            SiretSummary.ud_c3.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_ud_c4_count = db.query(SiretSummary).filter(
            SiretSummary.ud_c4.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_idcc_count = db.query(SiretSummary).filter(
            SiretSummary.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()

        print(f"  • FD C3 avec 'nan': {summary_fd_c3_count}")
        print(f"  • FD C4 avec 'nan': {summary_fd_c4_count}")
        print(f"  • UD C3 avec 'nan': {summary_ud_c3_count}")
        print(f"  • UD C4 avec 'nan': {summary_ud_c4_count}")
        print(f"  • IDCC avec 'nan': {summary_idcc_count}")

        # Nettoyer FD C3
        if summary_fd_c3_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.fd_c3.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd_c3=None)
            )
            print(f"  ✅ {summary_fd_c3_count} valeurs FD C3 nettoyées")

        # Nettoyer FD C4
        if summary_fd_c4_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.fd_c4.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd_c4=None)
            )
            print(f"  ✅ {summary_fd_c4_count} valeurs FD C4 nettoyées")

        # Nettoyer UD C3
        if summary_ud_c3_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.ud_c3.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud_c3=None)
            )
            print(f"  ✅ {summary_ud_c3_count} valeurs UD C3 nettoyées")

        # Nettoyer UD C4
        if summary_ud_c4_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.ud_c4.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud_c4=None)
            )
            print(f"  ✅ {summary_ud_c4_count} valeurs UD C4 nettoyées")

        # Nettoyer IDCC
        if summary_idcc_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )
            print(f"  ✅ {summary_idcc_count} valeurs IDCC nettoyées")

        # Commit toutes les modifications
        db.commit()

        print("\n" + "=" * 70)
        print("✅ Nettoyage terminé avec succès!")

        # Calculer le total
        total_cleaned = (
            inv_fd_count + inv_ud_count + inv_idcc_count +
            pv_fd_count + pv_ud_count + pv_idcc_count +
            summary_fd_c3_count + summary_fd_c4_count +
            summary_ud_c3_count + summary_ud_c4_count + summary_idcc_count
        )
        print(f"📊 Total de valeurs 'nan' nettoyées: {total_cleaned}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erreur lors du nettoyage: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

    return True

if __name__ == "__main__":
    success = clean_nan_values()
    sys.exit(0 if success else 1)
