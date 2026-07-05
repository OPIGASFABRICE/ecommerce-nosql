"""
redis_loader.py
------------------
Injection dans Redis :
  1. Sorted Set "top_products" (classement ventes en temps réel)
  2. Simulation de sessions actives (Hash + TTL 30 min)

Tout passe par un pipeline Redis (envoi groupé), jamais une commande
réseau par ligne du CSV.
"""

import os
import time
import pandas as pd
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
BATCH_SIZE = int(os.environ.get("REDIS_BATCH_SIZE", 5000))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 1800))  # 30 min


def get_client(host: str = REDIS_HOST, port: int = REDIS_PORT) -> redis.Redis:
    return redis.Redis(host=host, port=port, decode_responses=True)


def load_top_products(df: pd.DataFrame, r: redis.Redis = None, batch_size: int = BATCH_SIZE):
    r = r or get_client()
    print("[Redis] Mise à jour du classement 'top_products'...")

    t0 = time.time()
    pipe = r.pipeline(transaction=False)
    ops_in_pipe = 0
    for row in df.itertuples(index=False):
        pipe.zincrby("top_products", int(row.quantity), row.product_id)
        ops_in_pipe += 1
        if ops_in_pipe >= batch_size:
            pipe.execute()
            pipe = r.pipeline(transaction=False)
            ops_in_pipe = 0
    if ops_in_pipe:
        pipe.execute()

    elapsed = time.time() - t0
    print(f"[Redis] Sorted Set 'top_products' mis à jour en {elapsed:.1f}s")

    top5 = r.zrevrange("top_products", 0, 4, withscores=True)
    print("[Redis] Top 5 produits :", top5)
    return {"elapsed_s": elapsed, "top5": top5}


def simulate_active_sessions(df: pd.DataFrame, r: redis.Redis = None, sample_size: int = 200, ttl_seconds: int = SESSION_TTL_SECONDS):
    """Simule des utilisateurs actuellement en ligne : un Hash par
    session, avec expiration (TTL) de 30 min, comme demandé.
    On échantillonne, car appliquer un TTL 'session active' aux ~95 000
    lignes historiques n'aurait pas de sens (ce ne sont pas des visites
    en cours) : ceci simule un instantané réaliste de trafic en direct."""
    r = r or get_client()
    eligible = df.loc[~df["is_anonymous"]]
    sample = eligible.sample(n=min(sample_size, len(eligible)), random_state=42)
    print(f"[Redis] Simulation de {len(sample)} sessions actives (TTL {ttl_seconds}s)...")

    pipe = r.pipeline(transaction=False)
    for row in sample.itertuples(index=False):
        session_key = f"session:{row.customer_id}"
        pipe.hset(
            session_key,
            mapping={
                "customer_id": row.customer_id,
                "last_product_viewed": row.product_id,
                "last_category": row.product_category,
                "cart_value": row.total_amount,
            },
        )
        pipe.expire(session_key, ttl_seconds)
    pipe.execute()
    print(f"[Redis] {len(sample)} sessions créées (TTL {ttl_seconds}s)")
    return {"sessions_created": len(sample)}


def load(df: pd.DataFrame, r: redis.Redis = None):
    r = r or get_client()
    top = load_top_products(df, r)
    sessions = simulate_active_sessions(df, r)
    return {"top_products": top, "sessions": sessions}
