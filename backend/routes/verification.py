"""Verification and risk endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from schemas.schemas import VerificationResultSchema, GraphResponseSchema
from services.risk_engine import run_verification
from services.graph_service import build_invoice_graph

router = APIRouter(tags=["Verification"])


@router.post("/invoices/{invoice_id}/verify", response_model=VerificationResultSchema)
async def verify_invoice(invoice_id: str):
    """Run the full multi-signal risk verification for an invoice."""
    try:
        return run_verification(invoice_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices/{invoice_id}/risk", response_model=VerificationResultSchema)
async def get_risk(invoice_id: str):
    """Get cached or re-run risk result for an invoice."""
    try:
        return run_verification(invoice_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices/{invoice_id}/graph", response_model=GraphResponseSchema)
async def get_invoice_graph(invoice_id: str):
    """Return a React Flow compatible graph for the invoice relationship network."""
    try:
        res = build_invoice_graph(invoice_id)
        if not res.nodes:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found in graph database")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

