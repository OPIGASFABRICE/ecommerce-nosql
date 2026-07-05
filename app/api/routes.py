"""
routes.py
-----------
Endpoints de l'API :
  - GET /aggregations/revenue-by-category
  - GET /aggregations/top-customers?limit=10
  - GET /aggregations/sales-over-time?granularity=month
  - GET /recommendations/customer/{customer_id}?depth=2&limit=10
  - GET /recommendations/product/{product_id}?limit=10

Toutes les routes (sauf /health) passent par le rate limiter Redis.
"""

from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.database import get_mongo_db, get_neo4j_driver, get_redis_client
from app.api.rate_limiter import rate_limit
from app.api import aggregations, recommendations

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# AGRÉGATIONS MONGODB
# ---------------------------------------------------------------------
@router.get("/aggregations/revenue-by-category", dependencies=[Depends(rate_limit)])
def revenue_by_category():
    db = get_mongo_db()
    return {"data": aggregations.revenue_by_category(db)}


@router.get("/aggregations/top-customers", dependencies=[Depends(rate_limit)])
def top_customers(limit: int = Query(10, ge=1, le=100)):
    db = get_mongo_db()
    return {"data": aggregations.top_customers(db, limit=limit)}


@router.get("/aggregations/sales-over-time", dependencies=[Depends(rate_limit)])
def sales_over_time(granularity: str = Query("month", pattern="^(day|month)$")):
    db = get_mongo_db()
    return {"data": aggregations.sales_over_time(db, granularity=granularity)}


# ---------------------------------------------------------------------
# RECOMMANDATIONS NEO4J
# ---------------------------------------------------------------------
@router.get("/recommendations/customer/{customer_id}", dependencies=[Depends(rate_limit)])
def recommend_for_customer(
    customer_id: str,
    depth: int = Query(2, ge=2, le=3, description="Profondeur du graphe : 2 ou 3 sauts"),
    limit: int = Query(10, ge=1, le=50),
):
    driver = get_neo4j_driver()
    try:
        results = recommendations.recommend_by_similar_customers(driver, customer_id, depth=depth, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not results:
        return {"customer_id": customer_id, "depth": depth, "data": [], "message": "Aucune recommandation trouvée (client inconnu ou pas assez d'historique)."}
    return {"customer_id": customer_id, "depth": depth, "data": results}


@router.get("/recommendations/product/{product_id}", dependencies=[Depends(rate_limit)])
def recommend_for_product(product_id: str, limit: int = Query(10, ge=1, le=50)):
    driver = get_neo4j_driver()
    results = recommendations.recommend_co_purchased(driver, product_id, limit=limit)
    return {"product_id": product_id, "data": results}


# ---------------------------------------------------------------------
# TOP VENTES REDIS (Sorted Set, mis à jour à l'injection)
# ---------------------------------------------------------------------
@router.get("/top-products", dependencies=[Depends(rate_limit)])
def top_products(limit: int = Query(10, ge=1, le=100)):
    r = get_redis_client()
    raw = r.zrevrange("top_products", 0, limit - 1, withscores=True)
    return {"data": [{"product_id": pid, "total_quantity_sold": int(score)} for pid, score in raw]}