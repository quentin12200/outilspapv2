from sqlalchemy import Column, Integer, String, Date, Boolean, JSON, Text, DateTime
from .db import Base

class PVEvent(Base):
    __tablename__ = "pv_events"
    id = Column(Integer, primary_key=True)
    siret = Column(String(14), index=True, nullable=False)
    cycle = Column(String(10), index=True, nullable=False)      # 'C3' / 'C4'
    date_pv = Column(Date)                                      # colonne P
    type = Column(String(255))                                  # contient "carence" si carence
    inscrits = Column(Integer)
    votants = Column(Integer)
    blancs_nuls = Column(Integer)
    cgt_voix = Column(Integer)
    cgt_siege = Column(Integer)
    autres_indics = Column(JSON)                                # SVE/score orga, etc.
    idcc = Column(String(20))
    fd = Column(String(80))
    ud = Column(String(80))
    departement = Column(String(5))
    raison_sociale = Column(Text)
    cp = Column(String(10))
    ville = Column(Text)

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

    date_pv_c3 = Column(Date)
    carence_c3 = Column(Boolean)
    inscrits_c3 = Column(Integer)
    votants_c3 = Column(Integer)
    cgt_voix_c3 = Column(Integer)

    date_pv_c4 = Column(Date)
    carence_c4 = Column(Boolean)
    inscrits_c4 = Column(Integer)
    votants_c4 = Column(Integer)
    cgt_voix_c4 = Column(Integer)

    statut_pap = Column(String(10))       # 'C3' / 'C4' / 'C3+C4' / 'Aucun'
    date_pv_max = Column(Date)
    date_pap_c5 = Column(Date)            # dernière invitation connue
    cgt_implantee = Column(Boolean)
