"""
rate_limiter.py
------------------
Rate limiting "fenêtre fixe" (fixed window) implémenté à la main avec
Redis INCR + EXPIRE, injecté comme dépendance FastAPI.

Principe :
  - clé = ratelimit:{ip}:{minute_courante}
  - à chaque requête : INCR (créé la clé à 1 si elle n'existe pas)
  - si c'est la 1ère requête de la fenêtre (valeur == 1), on pose un TTL
    de 60s sur la clé -> elle s'auto-détruit à la fin de la minute
  - si le compteur dépasse la limite -> HTTP 429

Limite du fixed-window (à mentionner à l'oral) : un client peut envoyer
2x la limite en rafale à la frontière entre deux fenêtres (ex: 60 requêtes
à 12:00:59 puis 60 autres à 12:01:00). Un sliding-window log serait plus
précis mais plus coûteux en mémoire Redis.
"""

import os
import time
from fastapi import Request, HTTPException

from app.api.database import get_redis_client

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 60))
WINDOW_SECONDS = 60


async def rate_limit(request: Request):
    r = get_redis_client()
    client_ip = request.client.host if request.client else "unknown"
    current_window = int(time.time() // WINDOW_SECONDS)
    key = f"ratelimit:{client_ip}:{current_window}"

    current_count = r.incr(key)
    if current_count == 1:
        r.expire(key, WINDOW_SECONDS)

    if current_count > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Trop de requêtes : limite de {RATE_LIMIT_PER_MINUTE}/minute dépassée. Réessaie dans quelques secondes.",
        )
    return True