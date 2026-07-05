"""
recommendations.py
---------------------
Requêtes Cypher de recommandation.

Deux stratégies :
  1. "Clients similaires" (collaborative filtering) : on part d'un client,
     on remonte vers les produits qu'il a achetés, on redescend vers
     d'autres clients ayant acheté les mêmes produits, puis on ressort
     leurs autres achats. La profondeur (2 ou 3) contrôle combien de
     fois on répète ce saut Produit<->Client avant de proposer une
     recommandation ("les amis de mes amis ont aussi acheté...").

  2. "Achetés ensemble" (market-basket) : à partir d'un produit, on
     cherche les autres produits achetés par le même client le même
     jour (notre proxy de "panier", vu que le CSV source est structuré
     1 ligne = 1 article, sans identifiant de panier explicite).

Les requêtes sont paramétrées ($customer_id, $limit...) : jamais de
concaténation de chaînes avec une entrée utilisateur (protection contre
l'injection Cypher).
"""

# ---------------------------------------------------------------------
# Stratégie 1 : clients similaires, profondeur ajustable (2 ou 3)
# ---------------------------------------------------------------------
_SIMILAR_CUSTOMERS_DEPTH_2 = """
MATCH (c:Customer {customer_id: $customer_id})-[:PURCHASED]->(:Product)<-[:PURCHASED]-(o:Customer)-[:PURCHASED]->(rec:Product)
WHERE NOT (c)-[:PURCHASED]->(rec)
RETURN rec.product_id AS product_id, rec.category AS category, count(DISTINCT o) AS score
ORDER BY score DESC
LIMIT $limit
"""

_SIMILAR_CUSTOMERS_DEPTH_3 = """
MATCH (c:Customer {customer_id: $customer_id})-[:PURCHASED]->(:Product)<-[:PURCHASED]-(:Customer)-[:PURCHASED]->(:Product)<-[:PURCHASED]-(o2:Customer)-[:PURCHASED]->(rec:Product)
WHERE NOT (c)-[:PURCHASED]->(rec)
RETURN rec.product_id AS product_id, rec.category AS category, count(DISTINCT o2) AS score
ORDER BY score DESC
LIMIT $limit
"""

_DEPTH_QUERIES = {2: _SIMILAR_CUSTOMERS_DEPTH_2, 3: _SIMILAR_CUSTOMERS_DEPTH_3}


def recommend_by_similar_customers(driver, customer_id: str, depth: int = 2, limit: int = 10):
    if depth not in _DEPTH_QUERIES:
        raise ValueError("depth doit être 2 ou 3")
    query = _DEPTH_QUERIES[depth]
    with driver.session() as session:
        result = session.run(query, customer_id=customer_id, limit=limit)
        return [dict(record) for record in result]


# ---------------------------------------------------------------------
# Stratégie 2 : produits achetés ensemble (même client, même jour)
# ---------------------------------------------------------------------
_CO_PURCHASE_QUERY = """
MATCH (c:Customer)-[r1:PURCHASED]->(p1:Product {product_id: $product_id})
MATCH (c)-[r2:PURCHASED]->(p2:Product)
WHERE r1.date = r2.date AND p2.product_id <> $product_id
RETURN p2.product_id AS product_id, p2.category AS category, count(DISTINCT c) AS score
ORDER BY score DESC
LIMIT $limit
"""


def recommend_co_purchased(driver, product_id: str, limit: int = 10):
    with driver.session() as session:
        result = session.run(_CO_PURCHASE_QUERY, product_id=product_id, limit=limit)
        return [dict(record) for record in result]