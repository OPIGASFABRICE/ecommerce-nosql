"""
validator.py
------------
Fonctions de validation pures, réutilisées par clean_data.py.
Séparées du pipeline pour être testables indépendamment (pytest)
et réutilisables ailleurs (ex: validation à l'injection dans l'API).
"""

from datetime import datetime
import re

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def is_valid_iso_date(value: str) -> bool:
    """Vérifie le format ISO ET que la date existe réellement
    (rejette 2026-00-99T99:99:99, qui matcherait un simple regex de format)."""
    if not isinstance(value, str) or not ISO_DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        return True
    except ValueError:
        return False


def clean_unit_price(value: str):
    """Nettoie et valide un prix unitaire.
    Retourne (float(prix), None) si valide, ou (None, motif_erreur) sinon.
    Gère le cas des prix contenant 'CFA' (ex: '122.84 CFA')."""
    if not isinstance(value, str):
        return None, "PRICE_NULL"
    cleaned = value.replace("CFA", "").strip()
    try:
        price = float(cleaned)
    except ValueError:
        return None, "PRICE_NOT_NUMERIC"
    if price <= 0:
        return None, "PRICE_ABERRANT_NEGATIVE_OR_ZERO"
    return price, None


def is_valid_quantity(value) -> bool:
    """Une quantité doit être un entier strictement positif."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def is_missing_customer_id(value) -> bool:
    """Détecte une transaction anonyme (customer_id manquant/vide)."""
    return not isinstance(value, str) or value.strip() == ""
