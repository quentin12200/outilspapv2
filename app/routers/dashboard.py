"""Routes serveur pour la page dashboard analytique."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import SiretSummary

router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_session)):
    total_sirets = db.query(func.count(SiretSummary.siret)).scalar() or 0
    sirets_c3 = db.query(func.count()).filter(SiretSummary.has_c3.is_(True)).scalar() or 0
    sirets_c4 = db.query(func.count()).filter(SiretSummary.has_c4.is_(True)).scalar() or 0
    invitations_c5 = (
        db.query(func.count()).filter(SiretSummary.date_pap_c5.isnot(None)).scalar() or 0
    )
    matches = (
        db.query(func.count())
        .filter(SiretSummary.has_match_c5_pv.is_(True))
        .scalar()
        or 0
    )

    presence_rows = (
        db.query(SiretSummary.presence, func.count())
        .group_by(SiretSummary.presence)
        .all()
    )
    presence_labels = [row[0] or "Aucune" for row in presence_rows]
    presence_values = [row[1] for row in presence_rows]

    dept_rows = (
        db.query(SiretSummary.departement, func.count())
        .filter(SiretSummary.departement.isnot(None))
        .group_by(SiretSummary.departement)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    dept_labels = [row[0] for row in dept_rows]
    dept_values = [row[1] for row in dept_rows]

    fd_rows = (
        db.query(SiretSummary.fd, func.count())
        .filter(SiretSummary.fd.isnot(None))
        .group_by(SiretSummary.fd)
        .order_by(func.count().desc())
        .all()
    )
    fd_labels = [row[0] for row in fd_rows]
    fd_values = [row[1] for row in fd_rows]

    context = {
        "request": request,
        "total_sirets": total_sirets,
        "sirets_c3": sirets_c3,
        "sirets_c4": sirets_c4,
        "invitations_c5": invitations_c5,
        "matches": matches,
        "presence_labels": json.dumps(presence_labels),
        "presence_values": json.dumps(presence_values),
        "dept_labels": json.dumps(dept_labels),
        "dept_values": json.dumps(dept_values),
        "fd_labels": json.dumps(fd_labels),
        "fd_values": json.dumps(fd_values),
    }
    return templates.TemplateResponse("dashboard.html", context)
