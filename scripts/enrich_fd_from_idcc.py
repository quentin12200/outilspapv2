#!/usr/bin/env python3
"""
Script pour enrichir automatiquement les FD manquantes à partir des IDCC.

Principe:
- Toutes les entreprises avec un IDCC DOIVENT avoir une FD
- Ce script utilise la correspondance IDCC→FD extraite de la base PV
- Il enrichit automatiquement les invitations qui ont un IDCC mais pas de FD
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import Invitation, PVEvent


def build_idcc_fd_mapping(session):
    """
    Construit la table de correspondance IDCC → FD depuis les PV.

    Pour chaque IDCC, on choisit la FD la plus fréquente.
    """
    print("📊 Construction du mapping IDCC → FD depuis les PV...")

    # Récupérer tous les couples (IDCC, FD) des PV
    pv_pairs = session.query(PVEvent.idcc, PVEvent.fd).filter(
        PVEvent.idcc.isnot(None),
        PVEvent.idcc != "",
        PVEvent.fd.isnot(None),
        PVEvent.fd != ""
    ).all()

    if not pv_pairs:
        print("⚠️  Aucun PV avec IDCC et FD trouvé dans la base")
        return None

    print(f"   Trouvé {len(pv_pairs)} PV avec IDCC et FD")

    # Grouper par IDCC et compter les FD
    idcc_to_fds = {}
    for idcc, fd in pv_pairs:
        idcc = idcc.strip()
        fd = fd.strip()
        if idcc not in idcc_to_fds:
            idcc_to_fds[idcc] = []
        idcc_to_fds[idcc].append(fd)

    # Pour chaque IDCC, choisir la FD la plus fréquente
    idcc_to_fd = {}
    conflicts = 0

    for idcc, fds in idcc_to_fds.items():
        fd_counter = Counter(fds)
        most_common_fd = fd_counter.most_common(1)[0][0]
        idcc_to_fd[idcc] = most_common_fd

        if len(fd_counter) > 1:
            conflicts += 1

    print(f"   ✓ {len(idcc_to_fd)} correspondances IDCC → FD créées")
    if conflicts > 0:
        print(f"   ⚠️  {conflicts} IDCC avec plusieurs FD possibles (choix le plus fréquent)")

    return idcc_to_fd


def save_mapping(mapping, output_file):
    """Sauvegarde le mapping dans un fichier JSON."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    output_data = {
        "description": "Table de correspondance IDCC → FD générée depuis la base PV",
        "generated_at": datetime.now().isoformat(),
        "total_entries": len(mapping),
        "mapping": mapping
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"   💾 Mapping sauvegardé: {output_file}")


def load_mapping(mapping_file):
    """Charge le mapping depuis un fichier JSON."""
    if not mapping_file.exists():
        return None

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mapping", {})
    except Exception as e:
        print(f"⚠️  Erreur lecture du mapping: {e}")
        return None


def enrich_invitations(session, idcc_to_fd):
    """
    Enrichit les invitations qui ont un IDCC mais pas de FD.
    """
    print("\n🔧 Enrichissement des invitations...")

    # Trouver les invitations avec IDCC mais sans FD
    invitations_to_enrich = session.query(Invitation).filter(
        Invitation.idcc.isnot(None),
        Invitation.idcc != "",
        (Invitation.fd.is_(None) | (Invitation.fd == ""))
    ).all()

    if not invitations_to_enrich:
        print("   ✓ Toutes les invitations avec IDCC ont déjà une FD")
        return 0

    print(f"   Trouvé {len(invitations_to_enrich)} invitations à enrichir")

    enriched = 0
    not_found = set()

    for invitation in invitations_to_enrich:
        idcc = invitation.idcc.strip()

        if idcc in idcc_to_fd:
            invitation.fd = idcc_to_fd[idcc]
            enriched += 1
        else:
            not_found.add(idcc)

    if enriched > 0:
        session.commit()
        print(f"   ✅ {enriched} invitations enrichies avec leur FD")

    if not_found:
        print(f"   ⚠️  {len(not_found)} IDCC sans correspondance dans la base PV:")
        for idcc in sorted(not_found)[:5]:
            print(f"      - IDCC {idcc}")
        if len(not_found) > 5:
            print(f"      ... et {len(not_found) - 5} autres")

    return enriched


def main():
    """Point d'entrée principal."""
    session = SessionLocal()

    try:
        print("=" * 80)
        print("ENRICHISSEMENT AUTOMATIQUE FD À PARTIR DES IDCC")
        print("=" * 80)
        print()
        print("Principe: Toutes les entreprises avec un IDCC DOIVENT avoir une FD")
        print()

        # Chemin du fichier de mapping
        mapping_file = Path(__file__).parent.parent / "app" / "data" / "idcc_fd_mapping.json"

        # Essayer de charger un mapping existant
        idcc_to_fd = load_mapping(mapping_file)

        if idcc_to_fd:
            print(f"📂 Mapping existant chargé: {len(idcc_to_fd)} entrées")
            print(f"   Fichier: {mapping_file}")
        else:
            # Construire le mapping depuis les PV
            idcc_to_fd = build_idcc_fd_mapping(session)

            if not idcc_to_fd:
                print("\n❌ Impossible de construire le mapping IDCC → FD")
                print("   La table Tous_PV est vide ou ne contient pas de données IDCC/FD")
                print()
                print("💡 Solution:")
                print("   1. Assurez-vous que la base papcse.db contient les données PV")
                print("   2. Réexécutez ce script")
                return 1

            # Sauvegarder le mapping
            save_mapping(idcc_to_fd, mapping_file)

        # Enrichir les invitations
        print()
        enriched = enrich_invitations(session, idcc_to_fd)

        print()
        print("=" * 80)
        print("✅ ENRICHISSEMENT TERMINÉ")
        print("=" * 80)
        print()

        if enriched > 0:
            print(f"✓ {enriched} invitations ont été enrichies avec leur FD")
        else:
            print("✓ Aucune invitation à enrichir (toutes ont déjà une FD)")

        return 0

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
