"""Validation des fichiers d'importation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Sequence, Tuple

import pandas as pd


@dataclass
class ValidationError:
    """Structure représentant une anomalie détectée."""

    field: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message, "severity": self.severity}


_REQUIRED_PV_COLUMNS = ("siret", "cycle")
_REQUIRED_INVIT_COLUMNS = ("siret", "date")
_ALLOWED_CYCLES = {"C3", "C4"}


def _column_lookup(df: pd.DataFrame, aliases: Sequence[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def _format_validation_report(errors: Iterable[ValidationError]) -> str:
    rows = []
    for error in errors:
        level = error.severity.upper()
        rows.append(f"[{level}] {error.field}: {error.message}")
    return "\n".join(rows)


def validate_pv_file(df: pd.DataFrame) -> Tuple[bool, List[ValidationError]]:
    errors: List[ValidationError] = []

    missing = [col for col in _REQUIRED_PV_COLUMNS if _column_lookup(df, [col]) is None]
    if missing:
        errors.append(
            ValidationError(
                field=", ".join(missing),
                message="Colonnes obligatoires manquantes pour les PV (siret, cycle).",
            )
        )
        return False, errors

    siret_col = _column_lookup(df, ["siret"]) or "siret"
    cycle_col = _column_lookup(df, ["cycle", "c", "type"]) or "cycle"
    date_col = _column_lookup(df, ["date_pv", "date", "pv_date", "date du pv"])

    sirets = df[siret_col].dropna()
    invalid_sirets = sirets[~sirets.astype(str).str.fullmatch(r"\d{14}")]
    if not invalid_sirets.empty:
        errors.append(
            ValidationError(
                field=siret_col,
                message=f"{len(invalid_sirets)} SIRET invalides (14 chiffres attendus).",
            )
        )

    cycles = df[cycle_col].dropna().astype(str).str.strip().str.upper()
    bad_cycles = cycles[~cycles.isin(_ALLOWED_CYCLES)]
    if not bad_cycles.empty:
        errors.append(
            ValidationError(
                field=cycle_col,
                message="Cycles autorisés: C3 ou C4.",
            )
        )

    if date_col:
        parsed_dates: list[Tuple[int, date]] = []
        for idx, raw in df[date_col].items():
            if pd.isna(raw) or raw == "":
                continue
            try:
                dt = pd.to_datetime(raw, dayfirst=True, errors="raise").date()
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        field=date_col,
                        message=f"Date invalide ligne {idx + 2}: {raw!r}",
                    )
                )
                continue
            if dt < date(2010, 1, 1):
                errors.append(
                    ValidationError(
                        field=date_col,
                        message=f"Date trop ancienne (avant 2010) ligne {idx + 2}.",
                        severity="warning",
                    )
                )
            if dt > datetime.utcnow().date():
                errors.append(
                    ValidationError(
                        field=date_col,
                        message=f"Date future ligne {idx + 2}.",
                        severity="warning",
                    )
                )
            parsed_dates.append((idx, dt))

    return (not any(err.severity == "error" for err in errors)), errors


def validate_invitation_file(df: pd.DataFrame) -> Tuple[bool, List[ValidationError]]:
    errors: List[ValidationError] = []

    missing = [col for col in _REQUIRED_INVIT_COLUMNS if _column_lookup(df, [col]) is None]
    if missing:
        errors.append(
            ValidationError(
                field=", ".join(missing),
                message="Colonnes obligatoires manquantes pour les invitations (siret, date).",
            )
        )
        return False, errors

    siret_col = _column_lookup(df, ["siret"]) or "siret"
    date_col = _column_lookup(df, ["date", "date_pap", "date c5", "date protocole"])

    sirets = df[siret_col].dropna()
    invalid_sirets = sirets[~sirets.astype(str).str.fullmatch(r"\d{14}")]
    if not invalid_sirets.empty:
        errors.append(
            ValidationError(
                field=siret_col,
                message=f"{len(invalid_sirets)} SIRET invalides (14 chiffres attendus).",
            )
        )

    if date_col:
        for idx, raw in df[date_col].items():
            if pd.isna(raw) or raw == "":
                continue
            try:
                dt = pd.to_datetime(raw, dayfirst=True, errors="raise").date()
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        field=date_col,
                        message=f"Date PAP invalide ligne {idx + 2}: {raw!r}",
                    )
                )
                continue
            if dt < date(2020, 1, 1):
                errors.append(
                    ValidationError(
                        field=date_col,
                        message=f"Date PAP suspecte (avant 2020) ligne {idx + 2}.",
                        severity="warning",
                    )
                )

    return (not any(err.severity == "error" for err in errors)), errors


__all__ = [
    "ValidationError",
    "validate_pv_file",
    "validate_invitation_file",
    "_format_validation_report",
]
