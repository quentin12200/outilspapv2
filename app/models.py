from sqlalchemy import Column, Integer, String, Date, Boolean, JSON, Text
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
    raison_sociale = Column(Text)
    departement = Column(String(5))
    fd = Column(String(80))
    source = Column(Text)                                        # RED / mail / etc.
    raw = Column(JSON)


class SiretSummary(Base):
    __tablename__ = "siret_summary"
    # 1 ligne par SIRET
    siret = Column(String(14), primary_key=True)
    raison_sociale = Column(Text)
    departement = Column(String(5), index=True)
    fd = Column(String(80), index=True)
    has_c3 = Column(Boolean, index=True)
    has_c4 = Column(Boolean, index=True)
    presence = Column(String(10), index=True)
    os_c3 = Column(Text)
    os_c4 = Column(Text)
    date_pv_c3 = Column(Date)
    date_pv_c4 = Column(Date)
    date_pv_last = Column(Date, index=True)
    date_pap_c5 = Column(Date, index=True)
    invitation_count = Column(Integer)
    pv_c3_count = Column(Integer)
    pv_c4_count = Column(Integer)
    has_match_c5_pv = Column(Boolean, index=True)
