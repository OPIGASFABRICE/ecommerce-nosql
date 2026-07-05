"""
aggregations.py
------------------
Requêtes d'agrégation MongoDB exposées par l'API.
Toutes utilisent le pipeline d'agrégation natif ($unwind, $group, $sort) :
aucune agrégation n'est faite côté Python (ce serait contre-productif et
hors-sujet pour une API censée démontrer la puissance de Mongo).
"""


def revenue_by_category(db):
    """CA total et nombre de commandes par catégorie de produit."""
    pipeline = [
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.category",
                "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.unit_price"]}},
                "orders": {"$sum": 1},
            }
        },
        {"$sort": {"revenue": -1}},
        {"$project": {"_id": 0, "category": "$_id", "revenue": {"$round": ["$revenue", 2]}, "orders": 1}},
    ]
    return list(db.orders.aggregate(pipeline))


def top_customers(db, limit: int = 10):
    """Classement des clients par montant total dépensé.
    Exclut les transactions anonymes (pas de customer_id)."""
    pipeline = [
        {"$match": {"is_anonymous": False}},
        {
            "$group": {
                "_id": "$customer_id",
                "total_spent": {"$sum": "$total_amount"},
                "orders_count": {"$sum": 1},
            }
        },
        {"$sort": {"total_spent": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "customer_id": "$_id", "total_spent": {"$round": ["$total_spent", 2]}, "orders_count": 1}},
    ]
    return list(db.orders.aggregate(pipeline))


def sales_over_time(db, granularity: str = "month"):
    """Évolution du CA dans le temps, agrégé par mois ou par jour."""
    date_format = "%Y-%m" if granularity == "month" else "%Y-%m-%d"
    pipeline = [
        {"$addFields": {"parsed_date": {"$dateFromString": {"dateString": "$date"}}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": date_format, "date": "$parsed_date"}},
                "revenue": {"$sum": "$total_amount"},
                "orders": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "period": "$_id", "revenue": {"$round": ["$revenue", 2]}, "orders": 1}},
    ]
    return list(db.orders.aggregate(pipeline))