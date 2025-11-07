#!/usr/bin/env python3
"""
Script de diagnostic pour comprendre pourquoi FD/UD/IDCC sont vides.
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import Invitation
from sqlalchemy import func

def diagnostic():
    session = SessionLocal()

    try:
        print("=" * 80)
        print("📊 DIAGNOSTIC FD/UD/IDCC")
        print("=" * 80)

        # Statistiques générales
        total = session.query(func.count(Invitation.id)).scalar() or 0
        print(f"\n✓ Total invitations: {total}")

        # Statistiques sur le champ raw
        with_raw = session.query(func.count(Invitation.id)).filter(Invitation.raw.isnot(None)).scalar() or 0
        print(f"✓ Invitations avec champ raw: {with_raw}")

        # Statistiques sur FD
        fd_null = session.query(func.count(Invitation.id)).filter(Invitation.fd.is_(None)).scalar() or 0
        fd_empty = session.query(func.count(Invitation.id)).filter(Invitation.fd == "").scalar() or 0
        fd_filled = session.query(func.count(Invitation.id)).filter(
            Invitation.fd.isnot(None),
            Invitation.fd != ""
        ).scalar() or 0

        print(f"\n📋 FD:")
        print(f"  • NULL: {fd_null}")
        print(f"  • Chaîne vide: {fd_empty}")
        print(f"  • Rempli: {fd_filled}")

        # Statistiques sur UD
        ud_null = session.query(func.count(Invitation.id)).filter(Invitation.ud.is_(None)).scalar() or 0
        ud_empty = session.query(func.count(Invitation.id)).filter(Invitation.ud == "").scalar() or 0
        ud_filled = session.query(func.count(Invitation.id)).filter(
            Invitation.ud.isnot(None),
            Invitation.ud != ""
        ).scalar() or 0

        print(f"\n📋 UD:")
        print(f"  • NULL: {ud_null}")
        print(f"  • Chaîne vide: {ud_empty}")
        print(f"  • Rempli: {ud_filled}")

        # Statistiques sur IDCC
        idcc_null = session.query(func.count(Invitation.id)).filter(Invitation.idcc.is_(None)).scalar() or 0
        idcc_empty = session.query(func.count(Invitation.id)).filter(Invitation.idcc == "").scalar() or 0
        idcc_filled = session.query(func.count(Invitation.id)).filter(
            Invitation.idcc.isnot(None),
            Invitation.idcc != ""
        ).scalar() or 0

        print(f"\n📋 IDCC:")
        print(f"  • NULL: {idcc_null}")
        print(f"  • Chaîne vide: {idcc_empty}")
        print(f"  • Rempli: {idcc_filled}")

        # Exemple d'une invitation avec raw
        print("\n" + "=" * 80)
        print("📄 EXEMPLE D'INVITATION AVEC RAW")
        print("=" * 80)

        sample_with_raw = session.query(Invitation).filter(Invitation.raw.isnot(None)).first()

        if sample_with_raw:
            print(f"\nID: {sample_with_raw.id}")
            print(f"SIRET: {sample_with_raw.siret}")
            print(f"FD: {repr(sample_with_raw.fd)}")
            print(f"UD: {repr(sample_with_raw.ud)}")
            print(f"IDCC: {repr(sample_with_raw.idcc)}")
            print(f"\nChamp RAW (clés disponibles):")
            if sample_with_raw.raw:
                for key in sorted(sample_with_raw.raw.keys()):
                    value = sample_with_raw.raw[key]
                    # Tronquer les valeurs trop longues
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"  • {key}: {repr(value)}")
            else:
                print("  (raw est vide)")
        else:
            print("\n⚠️  Aucune invitation avec champ raw trouvée !")

        # Exemple d'une invitation sans FD/UD/IDCC
        print("\n" + "=" * 80)
        print("📄 EXEMPLE D'INVITATION SANS FD/UD/IDCC")
        print("=" * 80)

        sample_empty = session.query(Invitation).filter(
            Invitation.fd.is_(None) | (Invitation.fd == "")
        ).first()

        if sample_empty:
            print(f"\nID: {sample_empty.id}")
            print(f"SIRET: {sample_empty.siret}")
            print(f"FD: {repr(sample_empty.fd)}")
            print(f"UD: {repr(sample_empty.ud)}")
            print(f"IDCC: {repr(sample_empty.idcc)}")
            print(f"Denomination: {sample_empty.denomination}")
            print(f"\nChamp RAW:")
            if sample_empty.raw:
                print("  (raw existe avec clés):")
                for key in sorted(sample_empty.raw.keys())[:10]:  # Limite à 10 clés
                    value = sample_empty.raw[key]
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"  • {key}: {repr(value)}")
            else:
                print("  (raw est None ou vide)")

        print("\n" + "=" * 80)
        print("💡 RECOMMANDATIONS")
        print("=" * 80)

        if with_raw == 0:
            print("\n❌ Problème : Aucune invitation n'a de champ 'raw'")
            print("   → Les données doivent être ré-importées avec le bon script d'import")
        elif fd_null + fd_empty == total:
            print("\n❌ Problème : Toutes les colonnes FD sont vides")
            if with_raw > 0:
                print("   → Le champ raw existe mais ne contient pas la clé 'fd'")
                print("   → Vérifiez la structure du fichier Excel importé")
        else:
            print("\n✓ Des données FD existent")
            print(f"  Couverture: {fd_filled}/{total} ({100*fd_filled/total:.1f}%)")

    finally:
        session.close()

if __name__ == "__main__":
    diagnostic()
