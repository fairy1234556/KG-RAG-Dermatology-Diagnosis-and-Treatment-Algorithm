from __future__ import annotations

from fastapi import APIRouter

from backend.app.api import health, kg_rag, knowledge_graph

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(knowledge_graph.router)
api_router.include_router(kg_rag.router)

