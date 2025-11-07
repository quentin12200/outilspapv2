#!/usr/bin/env python3
"""
Script pour générer la table de correspondance IDCC → FD à partir de la base de données PV.

Ce script analyse tous les PV (Tous_PV) et crée un fichier JSON avec la correspondance
IDCC → FD qui sera utilisé par l'application pour enrichir automatiquement les invitations.

Usage:
    python scripts/generate_idcc_fd_mapping.py
"""

import sys
import os
import json
from collections import Counter
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import PVEvent


def build_idcc_fd_mapping():
    """
    Extrait la correspondance IDCC → FD à partir de la base de données PV.

    Pour chaque IDCC, on choisit la FD la plus fréquente parmi tous les PV.
    """
    session = SessionLocal()

    try:
        print("=" * 80)
        print("GÉNÉRATION DE LA TABLE DE CORRESPONDANCE IDCC → FD")
        print("=" * 80)
        print()

        # Récupérer tous les PV ayant un IDCC et une FD non vides
        print("Récupération des PV avec IDCC et FD renseignés...")
        pvs = session.query(PVEvent.idcc, PVEvent.fd).filter(
            PVEvent.idcc.isnot(None),
            PVEvent.idcc != "",
            PVEvent.fd.isnot(None),
            PVEvent.fd != ""
        ).all()

        print(f"✓ {len(pvs)} PV trouvés avec IDCC et FD")
        print()

        # Compter les occurrences de chaque couple (IDCC, FD)
        idcc_fd_pairs = [(pv.idcc.strip(), pv.fd.strip()) for pv in pvs if pv.idcc and pv.fd]

        # Grouper par IDCC et compter les FD
        idcc_to_fds = {}
        for idcc, fd in idcc_fd_pairs:
            if idcc not in idcc_to_fds:
                idcc_to_fds[idcc] = []
            idcc_to_fds[idcc].append(fd)

        # Pour chaque IDCC, choisir la FD la plus fréquente
        idcc_to_fd_mapping = {}
        conflicts = []

        print("Construction de la table de correspondance...")
        for idcc, fds in sorted(idcc_to_fds.items()):
            fd_counter = Counter(fds)
            most_common_fd, count = fd_counter.most_common(1)[0]
            idcc_to_fd_mapping[idcc] = most_common_fd

            if len(fd_counter) > 1:
                # Plusieurs FD pour le même IDCC
                conflicts.append({
                    "idcc": idcc,
                    "fds": dict(fd_counter),
                    "choix": most_common_fd
                })

        print(f"✓ Table de correspondance créée avec {len(idcc_to_fd_mapping)} entrées")
        print()

        # Afficher les conflits s'il y en a
        if conflicts:
            print(f"⚠️  {len(conflicts)} IDCC avec plusieurs FD possibles:")
            print()
            for conflict in conflicts[:10]:  # Afficher les 10 premiers
                print(f"  IDCC {conflict['idcc']}:")
                for fd, count in sorted(conflict['fds'].items(), key=lambda x: -x[1]):
                    marker = "→" if fd == conflict['choix'] else " "
                    print(f"    {marker} {fd}: {count} PV")
            if len(conflicts) > 10:
                print(f"  ... et {len(conflicts) - 10} autres conflits")
            print()

        # Sauvegarder dans un fichier JSON
        output_file = Path(__file__).parent.parent / "app" / "data" / "idcc_fd_mapping.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "description": "Table de correspondance IDCC → FD générée automatiquement à partir de la base PV",
            "generated_at": None,  # Sera rempli avec la date de génération
            "total_entries": len(idcc_to_fd_mapping),
            "conflicts": len(conflicts),
            "mapping": idcc_to_fd_mapping,
            "conflict_details": conflicts if conflicts else []
        }

        # Ajouter la date de génération
        from datetime import datetime
        output_data["generated_at"] = datetime.now().isoformat()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Fichier généré: {output_file}")
        print()

        # Afficher un échantillon de la correspondance
        print("Échantillon de la correspondance (10 premiers IDCC):")
        print()
        for idcc, fd in sorted(idcc_to_fd_mapping.items())[:10]:
            print(f"  IDCC {idcc:6} → {fd}")

        if len(idcc_to_fd_mapping) > 10:
            print(f"  ... et {len(idcc_to_fd_mapping) - 10} autres correspondances")

        print()
        print("=" * 80)
        print("GÉNÉRATION TERMINÉE")
        print("=" * 80)

    finally:
        session.close()


if __name__ == "__main__":
    build_idcc_fd_mapping()
