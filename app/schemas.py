from datetime import date
from typing import Optional

from pydantic import BaseModel


class SiretSummaryOut(BaseModel):
    siret: str
    raison_sociale: Optional[str]
    departement: Optional[str]
    fd: Optional[str]
    has_c3: Optional[bool]
    has_c4: Optional[bool]
    presence: Optional[str]
    os_c3: Optional[str]
    os_c4: Optional[str]
    date_pv_c3: Optional[date]
    date_pv_c4: Optional[date]
    date_pv_last: Optional[date]
    date_pap_c5: Optional[date]
    invitation_count: Optional[int]
    pv_c3_count: Optional[int]
    pv_c4_count: Optional[int]
    has_match_c5_pv: Optional[bool]

    class Config:
        from_attributes = True
