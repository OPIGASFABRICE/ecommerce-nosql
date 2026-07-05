"""
database.py
-------------
Connexions partagées aux 3 bases, utilisées par les routes de l'API.
(Rempli à l'étape "API" du projet — squelette fonctionnel dès maintenant
pour que la structure du dossier soit correcte.)
"""

import os
from pymongo import MongoClient
from neo4j import GraphDatabase
import redis

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0",
)
MONGO_DB = os.environ.get("MONGO_DB", "ecommerce")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

_mongo_client = None
_neo4j_driver = None
_redis_client = None


def get_mongo_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
    return _mongo_client[MONGO_DB]


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _neo4j_driver


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis_client
