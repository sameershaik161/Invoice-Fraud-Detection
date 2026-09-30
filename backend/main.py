"""
InvoiceFactoringGuard — FastAPI application entry point.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
import data_store
from routes.invoices import router as invoices_router
from routes.verification import router as verification_router
from routes.analytics import router as analytics_router
from routes.investigation import router as investigation_router
from routes.copilot import router as copilot_router
from services.graph_service import close_neo4j, initialize_neo4j, neo4j_is_connected

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting InvoiceFactoringGuard…")
    data_store.load_all()
    log.info("Data store ready.")
    initialize_neo4j()
    yield
    close_neo4j()
    log.info("Shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "An explainable multi-lender invoice intelligence and double-financing prevention platform. "
        "Built on synthetic hackathon data — not real banking or GST records."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(invoices_router, prefix=settings.API_PREFIX)
app.include_router(verification_router, prefix=settings.API_PREFIX)
app.include_router(analytics_router, prefix=settings.API_PREFIX)
app.include_router(investigation_router, prefix=settings.API_PREFIX)
app.include_router(copilot_router, prefix=settings.API_PREFIX)


@app.get("/api/health", tags=["Health"])
async def health():
    invoices_loaded = not data_store.get("invoices").empty
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "data_loaded": invoices_loaded,
        "neo4j_enabled": neo4j_is_connected(),
    }


@app.get("/api/demo/invoice", tags=["Demo"])
async def demo_invoice():
    """Return the canonical high-risk demo invoice ID for the live demo."""
    return {"demo_invoice_id": "INV-2026-02970"}
