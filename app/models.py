from sqlalchemy import Column, Integer, String, Boolean, Text, Date, DateTime, Float, JSON
from sqlalchemy.orm import synonym
from .db import Base


class PVEvent(Base):
    __tablename__ = "Tous_PV"

    # Identifiant principal présent dans la base livrée
    id = Column("id_pv", Integer, primary_key=True, autoincrement=False)
    id_pv = synonym("id")

    # Colonnes de base - respecter exactement les intitulés SQLite
    cycle = Column("Cycle", String(10), index=True)
    siret = Column(String(14), index=True)
    fd = Column("FD", String(80))
    idcc = Column("idcc", String(20))
    raison_sociale = Column("raison_sociale", Text)
    cp = Column("cp", String(10))
    ville = Column("ville", Text)
    ud = Column("UD", String(80))
    region = Column("Région", String(100))
    institution = Column("institution", String(100))
    # Ancienne colonne « type » (CSE / CAR) -> conservée pour compatibilité
    type = synonym("institution")
    oetamic = Column("OETAMIC", String(100))
    deno_coll = Column("deno_coll", Text)

    # Dates et scrutin
    date_pv = Column("date_scrutin", String(32))
    duree_mandat = Column("duree_mandat", Float)
    date_prochain_scrutin = Column("date_prochain_scrutin", String(32))
    quadrimestre_scrutin = Column("Quadrimestre_scrutin", String(20))

    # Résultats du scrutin
    inscrits = Column("num_inscrits", Float)
    votants = Column("num_votants", Float)
    sve = Column("num_sve", Float)
    tx_participation_pv = Column("Tx_Part._PV", Float)

    # Scores des syndicats au PV
    cgt_voix = Column("score_CGT", Float)
    score_cgt = synonym("cgt_voix")

    cfdt_voix = Column("score_CFDT", Float)
    score_cfdt = synonym("cfdt_voix")

    fo_voix = Column("score_FO", Float)
    score_fo = synonym("fo_voix")

    cftc_voix = Column("score_CFTC", Float)
    score_cftc = synonym("cftc_voix")

    cgc_voix = Column("score_CGC", Float)
    score_cgc = synonym("cgc_voix")

    unsa_voix = Column("score_UNSA", Float)
    score_unsa = synonym("unsa_voix")

    sud_voix = Column("score_SOLIDAIRE", Float)
    solidaire_voix = synonym("sud_voix")
    score_solidaire = synonym("sud_voix")

    autre_voix = Column("score_AUTRE", Float)
    score_autre = synonym("autre_voix")

    # Présence syndicats au PV
    controle = Column("Contrôle", String(50))
    presence_cgt_pv = Column("Présence_CGT_PV", String(10))
    pres_pv_cgt = Column("PRES_PV_CGT", String(10))
    pres_pv_cfdt = Column("PRES_PV_CFDT", String(10))
    pres_pv_fo = Column("PRES_PV_FO", String(10))
    pres_pv_cftc = Column("PRES_PV_CFTC", String(10))
    pres_pv_cgc = Column("PRES_PV_CGC", String(10))
    pres_pv_unsa = Column("PRES_PV_UNSA", String(10))
    pres_pv_sud = Column("PRES_PV_SUD", String(10))
    pres_pv_autre = Column("PRES_PV_AUTRE", String(10))

    # Composition des effectifs
    ouvriers = Column("Ouvriers", Float)
    employes = Column("Employés", Float)
    techniciens = Column("Techniciens", Float)
    maitrises = Column("Maitrises", Float)
    ingenieurs = Column("Ingénieurs", Float)
    cadres = Column("Cadres", Float)
    pct_inscrits_ictam = Column("%_Inscrits_ICTAM", Float)

    # Informations agrégées SIRET
    compte_siret = Column("Compte_siret", Float)
    compte_siret_cgt = Column("Compte_siret_CGT", Float)
    effectif_siret = Column("Effectif_Siret", Float)
    tranche1_effectif = Column("tranche1_effectif", String(50))
    tranche2_effectif = Column("tranche2_effectif", String(50))
    ul = Column("UL", String(100))
    votants_siret = Column("Votants_Siret", Float)
    nb_college_siret = Column("Nb_Collège_Siret", Float)
    sve_siret = Column("SVE_Siret", Float)
    tx_participation_siret = Column("TX_Part._Siret", Float)
    siret_moins_50 = Column("Siret_moins_50", Float)
    college = Column("Collège", String(100))
    presence_cgt_siret = Column("Présence_CGT_Siret", String(10))
    compo_college = Column("Compo_collège", Text)

    # Scores agrégés SIRET
    score_siret_cgt = Column("score_SIRET_CGT", Float)
    score_siret_cfdt = Column("score_SIRET_CFDT", Float)
    score_siret_fo = Column("score_SIRET_FO", Float)
    score_siret_cftc = Column("score_SIRET_CFTC", Float)
    score_siret_cgc = Column("score_SIRET_CGC", Float)
    score_siret_unsa = Column("score_SIRET_UNSA", Float)
    score_siret_sud = Column("score_SIRET_SUD", Float)
    score_siret_autre = Column("score_SIRET_AUTRE", Float)

    # Présence agrégée SIRET
    pres_siret_cgt = Column("PRES_SIRET_CGT", String(10))
    pres_siret_cfdt = Column("PRES_SIRET_CFDT", String(10))
    pres_siret_fo = Column("PRES_SIRET_FO", String(10))
    pres_siret_cftc = Column("PRES_SIRET_CFTC", String(10))
    pres_siret_cgc = Column("PRES_SIRET_CGC", String(10))
    pres_siret_unsa = Column("PRES_SIRET_UNSA", String(10))
    pres_siret_sud = Column("PRES_SIRET_SUD", String(10))
    pres_siret_autre = Column("PRES_SIRET_AUTRE", String(10))
    pres_cgt_tous_pv_siret = Column("Pres_CGT_Tous_PV_Siret", String(10))

    # Pourcentages SIRET
    pct_siret_cgt = Column("%_Siret_CGT", Float)
    pct_siret_cfdt = Column("%_Siret_CFDT", Float)
    pct_siret_fo = Column("%_Siret_FO", Float)
    pct_siret_cgc = Column("%_Siret_CGC", Float)

    # Informations SIREN
    siren = Column("siren", String(9))
    effectif_siren = Column("Effectif_Siren", Float)
    tranche_effectif_siren = Column("Tranche_effectif_SIREN", String(50))
    cpte_siren = Column("Cpte_Siren", Float)
    siren_votants = Column("Siren votants", Float)
    siren_sve = Column("Siren SVE", Float)
    siren_voix_cgt = Column("Siren voix CGT", Float)
    siren_score_cgt = Column("Siren Score CGT", Float)
    siren_voix_cfdt = Column("Siren voix CFDT", Float)
    siren_voix_fo = Column("Siren voix FO", Float)
    siren_voix_cftc = Column("Siren voix CFTC", Float)
    siren_voix_cgc = Column("Siren voix CGC", Float)

    # Informations RED
    idcc_red = Column("IDCC_RED", String(20))
    fd_code = Column("fd_Code", String(20))
    cr_code = Column("cr_Code", String(20))

    # CAC 40 / SBF 120
    code_sbf120 = Column("Code SBF_120", String(50))
    codes_sbf120_cac40 = Column("Codes SBF_120_(120360) CAC_40_(120400)", String(120))
    est_cac40_sbf120 = Column("O/N CAC40/SBF120", String(10))
    nom_groupe_sbf120 = Column("Nom_Groupe_SBF_120", Text)

    # Dates et divers
    date_visite_syndicat = Column("Date_visite_syndicat", String(32))
    date_formation = Column("Date_formation", String(32))
    annee_prochain = Column("ANNÉE_PROCHAIN", Float)
    binaire = Column("binaire", Float)

    # Compatibilité : certains appels hérités utilisent « departement ».
    departement = synonym("ud")


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    siret = Column(String(14), index=True, nullable=False)
    date_invit = Column(Date, nullable=False)                    # date PAP C5
    source = Column(Text)                                        # RED / mail / etc.
    raw = Column(JSON)

    # Données enrichies depuis l'API Sirene
    denomination = Column(Text)                                  # Raison sociale
    enseigne = Column(Text)                                      # Enseigne commerciale
    adresse = Column(Text)                                       # Adresse complète
    code_postal = Column(String(10))
    commune = Column(Text)
    activite_principale = Column(String(10))                     # Code NAF
    libelle_activite = Column(Text)                              # Libellé de l'activité
    tranche_effectifs = Column(String(5))                        # Code tranche
    effectifs_label = Column(Text)                               # Libellé de la tranche
    est_siege = Column(Boolean)                                  # True si siège social
    est_actif = Column(Boolean)                                  # True si établissement actif
    categorie_entreprise = Column(String(10))                    # PME, ETI, GE...
    date_enrichissement = Column(DateTime)                       # Date du dernier enrichissement


class SiretSummary(Base):
    __tablename__ = "siret_summary"
    # 1 ligne par SIRET
    siret = Column(String(14), primary_key=True)
    raison_sociale = Column(Text)
    idcc = Column(String(20))
    fd_c3 = Column(String(80))
    fd_c4 = Column(String(80))
    ud_c3 = Column(String(80))
    ud_c4 = Column(String(80))
    dep = Column(String(5))
    cp = Column(String(10))
    ville = Column(Text)
    region = Column(String(100))
    ul = Column(String(100))

    # Cycle 3 - CGT
    date_pv_c3 = Column(Date)
    carence_c3 = Column(Boolean)
    inscrits_c3 = Column(Integer)
    votants_c3 = Column(Integer)
    cgt_voix_c3 = Column(Integer)

    # Cycle 3 - Autres syndicats
    cfdt_voix_c3 = Column(Integer)
    fo_voix_c3 = Column(Integer)
    cftc_voix_c3 = Column(Integer)
    cgc_voix_c3 = Column(Integer)
    unsa_voix_c3 = Column(Integer)
    sud_voix_c3 = Column(Integer)
    solidaire_voix_c3 = Column(Integer)
    autre_voix_c3 = Column(Integer)

    # Cycle 4 - CGT
    date_pv_c4 = Column(Date)
    carence_c4 = Column(Boolean)
    inscrits_c4 = Column(Integer)
    votants_c4 = Column(Integer)
    cgt_voix_c4 = Column(Integer)

    # Cycle 4 - Autres syndicats
    cfdt_voix_c4 = Column(Integer)
    fo_voix_c4 = Column(Integer)
    cftc_voix_c4 = Column(Integer)
    cgc_voix_c4 = Column(Integer)
    unsa_voix_c4 = Column(Integer)
    sud_voix_c4 = Column(Integer)
    solidaire_voix_c4 = Column(Integer)
    autre_voix_c4 = Column(Integer)

    # Informations agrégées SIRET
    effectif_siret = Column(Integer)
    tranche1_effectif = Column(String(50))
    tranche2_effectif = Column(String(50))
    siret_moins_50 = Column(Boolean)
    nb_college_siret = Column(Integer)

    # Scores agrégés tous cycles
    score_siret_cgt = Column(Integer)
    score_siret_cfdt = Column(Integer)
    score_siret_fo = Column(Integer)
    score_siret_cftc = Column(Integer)
    score_siret_cgc = Column(Integer)
    score_siret_unsa = Column(Integer)
    score_siret_sud = Column(Integer)
    score_siret_autre = Column(Integer)

    # Pourcentages SIRET
    pct_siret_cgt = Column(Float)
    pct_siret_cfdt = Column(Float)
    pct_siret_fo = Column(Float)
    pct_siret_cgc = Column(Float)

    # Présence syndicats
    presence_cgt_siret = Column(Boolean)
    pres_siret_cgt = Column(Boolean)
    pres_siret_cfdt = Column(Boolean)
    pres_siret_fo = Column(Boolean)
    pres_siret_cftc = Column(Boolean)
    pres_siret_cgc = Column(Boolean)
    pres_siret_unsa = Column(Boolean)
    pres_siret_sud = Column(Boolean)
    pres_siret_autre = Column(Boolean)

    # Informations SIREN (groupe)
    siren = Column(String(9))
    effectif_siren = Column(Integer)
    tranche_effectif_siren = Column(String(50))
    siren_score_cgt = Column(Float)

    # Informations CAC 40 / SBF 120
    est_cac40_sbf120 = Column(String(10))
    nom_groupe_sbf120 = Column(Text)

    # Statuts et dates
    statut_pap = Column(String(10))       # 'C3' / 'C4' / 'C3+C4' / 'Aucun'
    date_pv_max = Column(Date)
    date_pap_c5 = Column(Date)            # dernière invitation connue
    cgt_implantee = Column(Boolean)
