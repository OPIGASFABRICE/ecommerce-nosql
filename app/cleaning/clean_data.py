"""
clean_data.py
--------------
Etape 1 du projet : Data Quality Pipeline.
Orchestration du nettoyage, en s'appuyant sur validator.py pour les règles.

Usage : python -m app.cleaning.clean_data
(depuis la racine du projet, avec le venv activé)

Anomalies traitées :
  1. Doublons stricts                       -> supprimés
  2. customer_id manquant                   -> conservé (flag is_anonymous),
                                                 exclu du graphe Neo4j
  3. quantity <= 0                          -> rejeté (log)
  4. unit_price corrompu (" CFA", négatif)  -> rejeté (log)
  5. transaction_date hors format ISO       -> rejeté (log)

Tout est vectorisé avec pandas (aucune boucle ligne par ligne avec I/O) ;
le journal d'erreurs est écrit en une seule fois, en bloc.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.cleaning.validator import (
    is_valid_iso_date,
    clean_unit_price,
    is_missing_customer_id,
)

BASE_DIR = Path(__file__).resolve().parents[2]  # racine du repo
RAW_PATH = BASE_DIR / "data" / "ecommerce_raw_transactions_dirty.csv"
CLEAN_PATH = BASE_DIR / "data" / "clean_transactions.csv"
ERROR_LOG_PATH = BASE_DIR / "data" / "errors.log"


def run(raw_path: Path = RAW_PATH, clean_path: Path = CLEAN_PATH, error_log_path: Path = ERROR_LOG_PATH):
    print(f"Lecture du fichier brut : {raw_path}")
    df = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    n_raw = len(df)
    print(f"  -> {n_raw:,} lignes chargées\n")

    errors = []

    # 1) Doublons stricts
    dup_mask = df.duplicated(keep="first")
    n_dup = int(dup_mask.sum())
    for tx_id in df.loc[dup_mask, "transaction_id"]:
        errors.append({"transaction_id": tx_id, "reason": "STRICT_DUPLICATE"})
    df = df.loc[~dup_mask].copy()
    print(f"1) Doublons stricts supprimés : {n_dup:,}")

    # 2) Quantity <= 0
    qty_numeric = pd.to_numeric(df["quantity"], errors="coerce")
    bad_qty_mask = qty_numeric.isna() | (qty_numeric <= 0)
    n_bad_qty = int(bad_qty_mask.sum())
    for tx_id in df.loc[bad_qty_mask, "transaction_id"]:
        errors.append({"transaction_id": tx_id, "reason": "QUANTITY_LTE_ZERO_OR_INVALID"})
    df = df.loc[~bad_qty_mask].copy()
    qty_numeric = qty_numeric.loc[~bad_qty_mask]
    print(f"2) Quantités incohérentes rejetées : {n_bad_qty:,}")

    # 3) unit_price corrompu
    price_results = df["unit_price"].apply(clean_unit_price)
    prices = price_results.apply(lambda t: t[0])
    price_reason = price_results.apply(lambda t: t[1])
    bad_price_mask = prices.isna()
    n_bad_price = int(bad_price_mask.sum())
    for tx_id, reason in zip(df.loc[bad_price_mask, "transaction_id"], price_reason[bad_price_mask]):
        errors.append({"transaction_id": tx_id, "reason": reason})
    df = df.loc[~bad_price_mask].copy()
    prices = prices.loc[~bad_price_mask]
    qty_numeric = qty_numeric.loc[~bad_price_mask]
    print(f"3) Prix corrompus (CFA / négatifs) rejetés : {n_bad_price:,}")

    # 4) transaction_date invalide
    valid_date_mask = df["transaction_date"].apply(is_valid_iso_date)
    n_bad_date = int((~valid_date_mask).sum())
    for tx_id in df.loc[~valid_date_mask, "transaction_id"]:
        errors.append({"transaction_id": tx_id, "reason": "INVALID_DATE_FORMAT"})
    df = df.loc[valid_date_mask].copy()
    prices = prices.loc[valid_date_mask]
    qty_numeric = qty_numeric.loc[valid_date_mask]
    print(f"4) Dates invalides rejetées : {n_bad_date:,}")

    # 5) customer_id manquant -> conservé, flaggé
    df["unit_price"] = prices.values
    df["quantity"] = qty_numeric.astype(int).values
    df["is_anonymous"] = df["customer_id"].apply(is_missing_customer_id)
    n_anonymous = int(df["is_anonymous"].sum())
    print(f"5) Transactions anonymes conservées (Mongo only) : {n_anonymous:,}")

    # Recalcul du total_amount (la colonne d'origine contenait "ERROR" pour
    # les lignes CFA -> on ne peut pas lui faire confiance)
    df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

    # Écriture en bloc
    df.to_csv(clean_path, index=False)
    with open(error_log_path, "w", encoding="utf-8") as f:
        f.write(f"# Rapport de nettoyage - {datetime.now().isoformat()}\n")
        f.write(f"# Lignes brutes: {n_raw} | Lignes valides: {len(df)} | Lignes rejetées: {len(errors)}\n\n")
        for e in errors:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print("\n" + "=" * 60)
    print("RÉSUMÉ DU NETTOYAGE")
    print("=" * 60)
    print(f"Lignes brutes            : {n_raw:,}")
    print(f"Lignes rejetées (total)  : {len(errors):,}")
    print(f"  - Doublons             : {n_dup:,}")
    print(f"  - Quantité invalide    : {n_bad_qty:,}")
    print(f"  - Prix corrompu        : {n_bad_price:,}")
    print(f"  - Date invalide        : {n_bad_date:,}")
    print(f"Lignes valides (propres) : {len(df):,}")
    print(f"  dont anonymes (Mongo)  : {n_anonymous:,}")
    print(f"  dont Neo4j-eligible    : {len(df) - n_anonymous:,}")
    print(f"\nFichier propre  -> {clean_path}")
    print(f"Journal erreurs -> {error_log_path}")
    return df


if __name__ == "__main__":
    run()
