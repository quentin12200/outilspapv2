from sqlalchemy import Column, Integer, String, Date, Boolean, JSON, Text, DateTime, Float
from .db import Base

class PVEvent(Base):
    __tablename__ = "pv_events"
    id = Column(Integer, primary_key=True)
    siret = Column(String(14), index=True, nullable=False)
    cycle = Column(String(10), index=True, nullable=False)      # 'C3' / 'C4'
    id_pv = Column(String(50))                                  # Identifiant unique du PV
    date_pv = Column(Date)                                      # date_scrutin
    type = Column(String(255))                                  # contient "carence" si carence

    # Métadonnées organisation
    idcc = Column(String(20))
    fd = Column(String(80))
    ud = Column(String(80))
    region = Column(String(100))
    ul = Column(String(100))
    departement = Column(String(5))
    raison_sociale = Column(Text)
    cp = Column(String(10))
    ville = Column(Text)

    # Informations PV
    institution = Column(String(100))
    oetamic = Column(String(100))
    deno_coll = Column(Text)                                    # Dénomination collective
    duree_mandat = Column(Integer)
    date_prochain_scrutin = Column(Date)
    quadrimestre_scrutin = Column(String(20))
    controle = Column(String(50))
    date_visite_syndicat = Column(Date)
    date_formation = Column(Date)
    college = Column(String(100))
    compo_college = Column(Text)

    # Résultats du scrutin
    inscrits = Column(Integer)                                  # num_inscrits
    votants = Column(Integer)                                   # num_votants
    sve = Column(Integer)                                       # num_sve (suffrages valablement exprimés)
    blancs_nuls = Column(Integer)
    tx_participation_pv = Column(Float)                         # Tx_Part._PV

    # Scores des syndicats au PV
    cgt_voix = Column(Integer)                                  # score_CGT
    cfdt_voix = Column(Integer)                                 # score_CFDT
    fo_voix = Column(Integer)                                   # score_FO
    cftc_voix = Column(Integer)                                 # score_CFTC
    cgc_voix = Column(Integer)                                  # score_CGC
    unsa_voix = Column(Integer)                                 # score_UNSA
    solidaire_voix = Column(Integer)                            # score_SOLIDAIRE
    autre_voix = Column(Integer)                                # score_AUTRE

    # Présence syndicats au PV (booléens)
    pres_pv_cgt = Column(Boolean)                               # Présence_CGT_PV
    pres_pv_cfdt = Column(Boolean)
    pres_pv_fo = Column(Boolean)
    pres_pv_cftc = Column(Boolean)
    pres_pv_cgc = Column(Boolean)
    pres_pv_unsa = Column(Boolean)
    pres_pv_sud = Column(Boolean)
    pres_pv_autre = Column(Boolean)

    # Sièges
    cgt_siege = Column(Integer)

    # Composition des effectifs du PV
    ouvriers = Column(Integer)
    employes = Column(Integer)
    techniciens = Column(Integer)
    maitrises = Column(Integer)
    ingenieurs = Column(Integer)
    cadres = Column(Integer)
    pct_inscrits_ictam = Column(Float)                          # %_Inscrits_ICTAM

    # Informations agrégées SIRET (répétées sur chaque ligne du PV)
    compte_siret = Column(Integer)                              # Nombre de PV pour ce SIRET
    compte_siret_cgt = Column(Integer)                          # Nombre de PV avec CGT
    effectif_siret = Column(Integer)
    tranche1_effectif = Column(String(50))
    tranche2_effectif = Column(String(50))
    votants_siret = Column(Integer)
    nb_college_siret = Column(Integer)
    sve_siret = Column(Integer)
    tx_participation_siret = Column(Float)
    siret_moins_50 = Column(Boolean)
    presence_cgt_siret = Column(Boolean)
    pres_cgt_tous_pv_siret = Column(Boolean)

    # Scores agrégés SIRET
    score_siret_cgt = Column(Integer)
    score_siret_cfdt = Column(Integer)
    score_siret_fo = Column(Integer)
    score_siret_cftc = Column(Integer)
    score_siret_cgc = Column(Integer)
    score_siret_unsa = Column(Integer)
    score_siret_sud = Column(Integer)
    score_siret_autre = Column(Integer)

    # Présence agrégée SIRET
    pres_siret_cgt = Column(Boolean)
    pres_siret_cfdt = Column(Boolean)
    pres_siret_fo = Column(Boolean)
    pres_siret_cftc = Column(Boolean)
    pres_siret_cgc = Column(Boolean)
    pres_siret_unsa = Column(Boolean)
    pres_siret_sud = Column(Boolean)
    pres_siret_autre = Column(Boolean)

    # Pourcentages SIRET
    pct_siret_cgt = Column(Float)                               # %_Siret_CGT
    pct_siret_cfdt = Column(Float)
    pct_siret_fo = Column(Float)
    pct_siret_cgc = Column(Float)

    # Informations SIREN (groupe)
    siren = Column(String(9))
    effectif_siren = Column(Integer)
    tranche_effectif_siren = Column(String(50))
    compte_siren = Column(Integer)
    siren_votants = Column(Integer)
    siren_sve = Column(Integer)
    siren_voix_cgt = Column(Integer)
    siren_score_cgt = Column(Float)
    siren_voix_cfdt = Column(Integer)
    siren_voix_fo = Column(Integer)
    siren_voix_cftc = Column(Integer)
    siren_voix_cgc = Column(Integer)

    # Informations RED
    idcc_red = Column(String(20))
    fd_code = Column(String(20))
    cr_code = Column(String(20))

    # Informations CAC 40 / SBF 120
    code_sbf120 = Column(String(50))
    codes_sbf120_cac40 = Column(String(100))
    est_cac40_sbf120 = Column(String(10))                       # O/N
    nom_groupe_sbf120 = Column(Text)

    # Informations diverses
    annee_prochain = Column(Integer)
    binaire = Column(String(50))

    # Ancien champ JSON pour compatibilité
    autres_indics = Column(JSON)

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
