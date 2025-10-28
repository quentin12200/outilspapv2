from pydantic import BaseModel
from datetime import date
from typing import Optional, List

class SiretSummaryOut(BaseModel):
    siret: str
    raison_sociale: Optional[str]
    idcc: Optional[str]
    fd_c3: Optional[str]
    fd_c4: Optional[str]
    ud_c3: Optional[str]
    ud_c4: Optional[str]
    dep: Optional[str]
    cp: Optional[str]
    ville: Optional[str]
    date_pv_c3: Optional[date]
    carence_c3: Optional[bool]
    inscrits_c3: Optional[int]
    votants_c3: Optional[int]
    cgt_voix_c3: Optional[int]
    date_pv_c4: Optional[date]
    carence_c4: Optional[bool]
    inscrits_c4: Optional[int]
    votants_c4: Optional[int]
    cgt_voix_c4: Optional[int]
    statut_pap: Optional[str]
    date_pv_max: Optional[date]
    date_pap_c5: Optional[date]
    cgt_implantee: Optional[bool]

    class Config:
        from_attributes = True
