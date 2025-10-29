"""Configuration centralisée du logging applicatif et d'audit."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    """Ajoute une coloration basique aux niveaux de logs."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        message = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"] if color else ""
        return f"{color}{message}{reset}"


def _resolve_log_path(raw_path: str) -> Path:
    """Return a writable log path, falling back to a temp directory if needed."""

    candidate = Path(raw_path)

    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if os.access(candidate.parent, os.W_OK):
            return candidate
    except OSError:
        pass

    tmp_root = Path(os.getenv("TMPDIR", tempfile.gettempdir())) / "papcse_logs"
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root / candidate.name


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Initialise les handlers de logging de l'application."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)

    if log_file:
        log_path = _resolve_log_path(log_file)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)

    for noisy in ("sqlalchemy.engine", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé après initialisation."""
    return logging.getLogger(name)


class AuditLogger:
    """Logger dédié aux événements sensibles (imports, exports, etc.)."""

    def __init__(self) -> None:
        raw_log_file = os.getenv("AUDIT_LOG_FILE", "logs/audit.log")
        self._logger = logging.getLogger("audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if self._logger.handlers:
            return

        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        log_path = _resolve_log_path(raw_log_file)

        try:
            handler = logging.FileHandler(log_path, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - environment dependent
            fallback = logging.StreamHandler()
            fallback.setFormatter(formatter)
            self._logger.addHandler(fallback)
            logging.getLogger(__name__).warning(
                "Impossible d'ouvrir le fichier de logs d'audit %s (%s). "
                "Bascule sur la sortie standard.",
                log_path,
                exc,
            )
        else:
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log_import(self, user: str, file_type: str, rows: int, success: bool) -> None:
        self._logger.info(
            "IMPORT user=%s type=%s rows=%s success=%s", user, file_type, rows, success
        )

    def log_export(self, user: Optional[str], resource: str, rows: int) -> None:
        self._logger.info("EXPORT user=%s resource=%s rows=%s", user, resource, rows)

    def log_build_summary(self, user: Optional[str], sirets: int, success: bool) -> None:
        self._logger.info(
            "REBUILD_SUMMARY user=%s sirets=%s success=%s", user, sirets, success
        )


audit_logger = AuditLogger()

__all__ = ["setup_logging", "get_logger", "audit_logger", "AuditLogger"]
