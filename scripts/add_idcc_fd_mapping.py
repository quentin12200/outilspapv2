#!/usr/bin/env python3
"""
Script pour ajouter ou modifier des correspondances IDCC → FD dans le mapping manuel.

Usage:
    python scripts/add_idcc_fd_mapping.py --idcc 1234 --fd "FTM-CGT"
    python scripts/add_idcc_fd_mapping.py --batch idcc_fd_list.json
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_mapping(mapping_file):
    """Charge le mapping existant ou crée un nouveau."""
    if mapping_file.exists():
        with open(mapping_file, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "description": "Table de correspondance IDCC → FD",
            "generated_at": datetime.now().isoformat(),
            "total_entries": 0,
            "mapping": {}
        }


def save_mapping(mapping_file, data):
    """Sauvegarde le mapping."""
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Mettre à jour les métadonnées
    data["total_entries"] = len(data["mapping"])
    data["updated_at"] = datetime.now().isoformat()
    
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_mapping(mapping_file, idcc, fd):
    """Ajoute ou met à jour une correspondance IDCC → FD."""
    data = load_mapping(mapping_file)
    
    idcc = str(idcc).strip()
    fd = fd.strip()
    
    if idcc in data["mapping"]:
        old_fd = data["mapping"][idcc]
        print(f"⚠️  IDCC {idcc} existe déjà avec FD '{old_fd}'")
        print(f"   Remplacement par '{fd}'")
    else:
        print(f"✅ Ajout de IDCC {idcc} → FD '{fd}'")
    
    data["mapping"][idcc] = fd
    save_mapping(mapping_file, data)
    
    return True


def add_batch(mapping_file, batch_file):
    """Ajoute plusieurs correspondances depuis un fichier JSON."""
    with open(batch_file, "r", encoding="utf-8") as f:
        batch_data = json.load(f)
    
    data = load_mapping(mapping_file)
    
    added = 0
    updated = 0
    
    for idcc, fd in batch_data.items():
        idcc = str(idcc).strip()
        fd = fd.strip()
        
        if idcc in data["mapping"]:
            if data["mapping"][idcc] != fd:
                print(f"⚠️  IDCC {idcc}: '{data['mapping'][idcc]}' → '{fd}'")
                updated += 1
        else:
            print(f"✅ IDCC {idcc} → '{fd}'")
            added += 1
        
        data["mapping"][idcc] = fd
    
    save_mapping(mapping_file, data)
    
    print(f"\n📊 Résumé:")
    print(f"   Ajoutés: {added}")
    print(f"   Mis à jour: {updated}")
    print(f"   Total dans le mapping: {len(data['mapping'])}")
    
    return True


def list_mapping(mapping_file):
    """Affiche le mapping actuel."""
    data = load_mapping(mapping_file)
    
    print("=" * 80)
    print("MAPPING IDCC → FD")
    print("=" * 80)
    print(f"Fichier: {mapping_file}")
    print(f"Total: {data.get('total_entries', 0)} entrées")
    print()
    
    if not data.get("mapping"):
        print("⚠️  Le mapping est vide")
        return
    
    for idcc in sorted(data["mapping"].keys(), key=lambda x: int(x) if x.isdigit() else 0):
        fd = data["mapping"][idcc]
        print(f"  IDCC {idcc:>5} → {fd}")


def main():
    parser = argparse.ArgumentParser(
        description="Gérer le mapping manuel IDCC → FD"
    )
    
    parser.add_argument(
        "--idcc",
        type=str,
        help="Code IDCC à ajouter/modifier"
    )
    
    parser.add_argument(
        "--fd",
        type=str,
        help="Code FD correspondant"
    )
    
    parser.add_argument(
        "--batch",
        type=str,
        help="Fichier JSON avec plusieurs correspondances {idcc: fd, ...}"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="Afficher le mapping actuel"
    )
    
    args = parser.parse_args()
    
    mapping_file = Path(__file__).parent.parent / "app" / "data" / "idcc_fd_mapping.json"
    
    if args.list:
        list_mapping(mapping_file)
        return 0
    
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            print(f"❌ Fichier introuvable: {batch_file}")
            return 1
        
        add_batch(mapping_file, batch_file)
        return 0
    
    if args.idcc and args.fd:
        add_mapping(mapping_file, args.idcc, args.fd)
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
