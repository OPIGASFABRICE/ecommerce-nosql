"""
sync_pipeline.py
------------------
Orchestrateur : lit data/clean_transactions.csv et déclenche
l'injection en masse dans les 3 bases (Mongo, Neo4j, Redis).

Usage : python -m app.injection.sync_pipeline
Prérequis : `docker compose up -d` doit tourner, et
            app/cleaning/clean_data.py doit déjà avoir été exécuté.
"""

from pathlib import Path
import pandas as pd

from app.injection import mongo_loader, neo4j_loader, redis_loader

BASE_DIR = Path(__file__).resolve().parents[2]
CLEAN_CSV = BASE_DIR / "data" / "clean_transactions.csv"


def load_clean_dataframe(path: Path = CLEAN_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["is_anonymous"] = df["is_anonymous"].map({"True": True, "False": False})
    df["quantity"] = df["quantity"].astype(int)
    df["unit_price"] = df["unit_price"].astype(float)
    df["total_amount"] = df["total_amount"].astype(float)
    return df


def run():
    print(f"Lecture de {CLEAN_CSV}...")
    df = load_clean_dataframe()
    print(f"-> {len(df):,} transactions propres chargées\n")

    mongo_stats = mongo_loader.load(df)
    print()
    neo4j_stats = neo4j_loader.load(df)
    print()
    redis_stats = redis_loader.load(df)

    print("\n=== Injection terminée dans les 3 bases ===")
    return {"mongo": mongo_stats, "neo4j": neo4j_stats, "redis": redis_stats}


if __name__ == "__main__":
    run()
