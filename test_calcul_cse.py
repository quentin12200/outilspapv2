#!/usr/bin/env python3
"""
Test du calcul CSE avec l'exemple du camarade :
1000 voix, 7 sièges
A=500, B=270, C=120, D=110
Résultat attendu : A=4, B=2, C=1, D=0
"""

from app.services.calcul_elus_cse import repartir_sieges_quotient_puis_plus_forte_moyenne

# Exemple du camarade
voix = {"A": 500, "B": 270, "C": 120, "D": 110}
nb_sieges = 7

print("=" * 60)
print("TEST CALCUL CSE - Exemple du camarade")
print("=" * 60)
print(f"\nVoix : {voix}")
print(f"Total voix : {sum(voix.values())}")
print(f"Sièges à répartir : {nb_sieges}")

print("\n--- ÉTAPE 1 : Quotient électoral (R2314-19) ---")
total_voix = sum(voix.values())
quotient = total_voix / nb_sieges
print(f"Quotient électoral = {total_voix} / {nb_sieges} = {quotient:.2f}")

sieges_quotient = {}
for orga, v in voix.items():
    s = int(v / quotient)
    sieges_quotient[orga] = s
    print(f"  {orga} : {v} voix / {quotient:.2f} = {s} siège(s)")

total_sieges_quotient = sum(sieges_quotient.values())
print(f"\nTotal attribué par quotient : {total_sieges_quotient} sièges")
print(f"Restent : {nb_sieges - total_sieges_quotient} sièges")

print("\n--- ÉTAPE 2 : Plus forte moyenne (R2314-20) ---")
print("Attribution des sièges restants...")

# Appel de la fonction
resultat = repartir_sieges_quotient_puis_plus_forte_moyenne(voix, nb_sieges)

print("\n--- RÉSULTAT FINAL ---")
for orga, sieges in sorted(resultat.items(), key=lambda x: x[1], reverse=True):
    pourcent = (voix[orga] / total_voix) * 100
    print(f"  {orga} : {sieges} siège(s) ({pourcent:.1f}% des voix)")

print("\n--- VÉRIFICATION ---")
attendu = {"A": 4, "B": 2, "C": 1, "D": 0}
print(f"Attendu : {attendu}")
print(f"Obtenu  : {resultat}")

if resultat == attendu:
    print("\n✅ TEST RÉUSSI ! Le calcul est conforme.")
else:
    print("\n❌ TEST ÉCHOUÉ ! Le calcul ne correspond pas.")
    for orga in voix.keys():
        if resultat.get(orga, 0) != attendu.get(orga, 0):
            print(f"   {orga} : attendu {attendu.get(orga, 0)}, obtenu {resultat.get(orga, 0)}")

print("=" * 60)
