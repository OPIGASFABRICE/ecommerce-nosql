"""
mongo_loader.py
-----------------
Injection en masse dans MongoDB (Replica Set).

Modélisation : chaque transaction du CSV nettoyé devient UN document
Mongo avec un tableau `items` imbriqué (ici, un seul item par document
puisque le CSV source est 1 ligne = 1 transaction = 1 article).
L'imbrication évite tout JOIN : une commande se lit en une seule requête.
"""

import os
import time
import pandas as pd
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0",
)
MONGO_DB = os.environ.get("MONGO_DB", "ecommerce")
BATCH_SIZE = int(os.environ.get("MONGO_BATCH_SIZE", 5000))


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_documents(df: pd.DataFrame):
    docs = []
    for row in df.itertuples(index=False):
        docs.append(
            {
                "_id": row.transaction_id,
                "customer_id": None if row.is_anonymous else row.customer_id,
                "is_anonymous": bool(row.is_anonymous),
                "date": row.transaction_date,
                "items": [
                    {
                        "product_id": row.product_id,
                        "category": row.product_category,
                        "quantity": int(row.quantity),
                        "unit_price": float(row.unit_price),
                    }
                ],
                "total_amount": float(row.total_amount),
            }
        )
    return docs


def load(df: pd.DataFrame, uri: str = MONGO_URI, db_name: str = MONGO_DB, batch_size: int = BATCH_SIZE):
    print("[MongoDB] Connexion au Replica Set...")
    client = MongoClient(uri)
    db = client[db_name]
    collection = db["orders"]

    # Index utiles aux futures agrégations (idempotent)
    collection.create_index("customer_id")
    collection.create_index("items.category")
    collection.create_index("date")

    docs = build_documents(df)
    print(f"[MongoDB] {len(docs):,} documents à insérer, par lots de {batch_size}")

    t0 = time.time()
    inserted, failed = 0, 0
    for batch in _chunks(docs, batch_size):
        operations = [InsertOne(d) for d in batch]
        try:
            # ordered=False : le lot continue même si un doc échoue
            # (ex: relance du script -> _id déjà présent)
            result = collection.bulk_write(operations, ordered=False)
            inserted += result.inserted_count
        except BulkWriteError as bwe:
            inserted += bwe.details.get("nInserted", 0)
            failed += len(bwe.details.get("writeErrors", []))

    elapsed = time.time() - t0
    print(f"[MongoDB] Terminé en {elapsed:.1f}s -> {inserted:,} insérés, {failed:,} échecs (doublons _id probables)")
    client.close()
    return {"inserted": inserted, "failed": failed, "elapsed_s": elapsed}
