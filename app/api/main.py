"""
main.py
---------
Point d'entrée FastAPI. Lancer avec :
  uvicorn app.api.main:app --reload --port 8000

TODO (prochaine étape) : brancher les vraies routes d'agrégation,
de recommandation et de rate limiting dans routes.py.
"""

from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="E-Commerce NoSQL API", version="0.1.0")
app.include_router(router)
