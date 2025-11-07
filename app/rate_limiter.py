"""
Rate limiter simple pour respecter les limites de l'API Sirene.
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """
    Rate limiter pour l'API Sirene INSEE.

    Limite par défaut : 30 requêtes/minute (accès public gratuit).
    Pour augmenter, passer à un plan payant sur le portail INSEE.
    """

    def __init__(self, max_requests: int = 30, time_window: int = 60):
        """
        Args:
            max_requests: Nombre max de requêtes autorisées
            time_window: Fenêtre de temps en secondes (défaut: 60s = 1 minute)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []  # Liste des timestamps de requêtes

        logger.info(
            f"Rate limiter initialisé : {max_requests} req/{time_window}s"
        )

    def wait_if_needed(self) -> float:
        """
        Attend si nécessaire pour respecter le rate limit.

        Returns:
            Temps d'attente en secondes (0 si pas d'attente nécessaire)
        """
        now = time.time()

        # Nettoyer les anciennes requêtes (en dehors de la fenêtre)
        self.requests = [
            req_time
            for req_time in self.requests
            if now - req_time < self.time_window
        ]

        # Si on a atteint la limite
        if len(self.requests) >= self.max_requests:
            # Calculer le temps d'attente jusqu'à ce que la plus ancienne requête sorte
            oldest_request = self.requests[0]
            wait_time = self.time_window - (now - oldest_request) + 0.1  # +0.1s de marge

            if wait_time > 0:
                logger.warning(
                    f"Rate limit atteint ({self.max_requests} req/{self.time_window}s). "
                    f"Attente de {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                return wait_time

        # Enregistrer cette requête
        self.requests.append(now)
        return 0.0

    def get_status(self) -> dict:
        """
        Retourne le statut actuel du rate limiter.

        Returns:
            Dict avec les infos : requests_used, requests_remaining, reset_in
        """
        now = time.time()

        # Nettoyer les anciennes requêtes
        self.requests = [
            req_time
            for req_time in self.requests
            if now - req_time < self.time_window
        ]

        requests_used = len(self.requests)
        requests_remaining = max(0, self.max_requests - requests_used)

        # Temps avant le reset
        if self.requests:
            oldest_request = self.requests[0]
            reset_in = self.time_window - (now - oldest_request)
        else:
            reset_in = 0

        return {
            "requests_used": requests_used,
            "requests_remaining": requests_remaining,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "reset_in_seconds": max(0, reset_in)
        }


# Instance globale pour l'API Sirene
# Pour accès public gratuit : 30 req/min
# Pour plan payant, augmenter max_requests (ex: 300 pour 300 req/min)
sirene_rate_limiter = APIRateLimiter(max_requests=28, time_window=60)
# Note: 28 au lieu de 30 pour garder une marge de sécurité
