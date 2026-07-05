"""
neo4j_loader.py
------------------
Injection en masse dans Neo4j : graphe (Customer)-[:PURCHASED]->(Product).

Les transactions anonymes (is_anonymous=True) sont exclues, comme
demandé par le sujet. UNWIND permet d'envoyer un lot entier de lignes
en UNE seule requête Cypher (au lieu d'une requête par ligne).
"""

import os
import time
import pandas as pd
from neo4j import GraphDatabase

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")
BATCH_SIZE = int(os.environ.get("NEO4J_BATCH_SIZE", 2000))

CYPHER_UPSERT_BATCH = """
UNWIND $rows AS row
MERGE (c:Customer {customer_id: row.customer_id})
MERGE (p:Product {product_id: row.product_id})
  ON CREATE SET p.category = row.category
MERGE (c)-[r:PURCHASED {transaction_id: row.transaction_id}]->(p)
  SET r.date = row.date, r.quantity = row.quantity
"""


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load(df: pd.DataFrame, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD, batch_size: int = BATCH_SIZE):
    print("[Neo4j] Connexion...")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    # Contraintes d'unicité -> index sous-jacent, rend les MERGE rapides
    with driver.session() as session:
        session.run("CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE")
        session.run("CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE")

    eligible = df.loc[~df["is_anonymous"]]
    print(f"[Neo4j] {len(eligible):,} transactions éligibles (customer_id présent)")

    rows = [
        {
            "customer_id": r.customer_id,
            "product_id": r.product_id,
            "category": r.product_category,
            "date": r.transaction_date,
            "quantity": int(r.quantity),
            "transaction_id": r.transaction_id,
        }
        for r in eligible.itertuples(index=False)
    ]

    t0 = time.time()
    with driver.session() as session:
        for batch in _chunks(rows, batch_size):
            session.run(CYPHER_UPSERT_BATCH, rows=batch)

    elapsed = time.time() - t0
    print(f"[Neo4j] Terminé en {elapsed:.1f}s -> {len(rows):,} relations PURCHASED traitées")
    driver.close()
    return {"relationships": len(rows), "elapsed_s": elapsed}
