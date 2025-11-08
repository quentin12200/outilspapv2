#!/usr/bin/env python3
"""
Script pour remplir les colonnes FD, UD, IDCC depuis le champ raw des invitations.

Ce script est utile si vous avez déjà importé des invitations PAP
et que les colonnes FD/UD ne sont pas remplies.
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.migrations import fill_invitation_columns_from_raw

if __name__ == "__main__":
    print("🔄 Remplissage des colonnes FD/UD/IDCC depuis le champ raw...")
    fill_invitation_columns_from_raw()
    print("✅ Terminé !")
