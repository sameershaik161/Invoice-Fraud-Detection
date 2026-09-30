from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

import data_store
from routes.invoices import _build_detail
from schemas.schemas import AuditEntrySchema, EvidenceItemSchema
from services.graph_service import build_invoice_graph
from services.risk_engine import run_verification

router = APIRouter(tags=["Investigation"])


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@router.get("/search")
async def search_entities(q: str = Query("", min_length=1), limit: int = Query(8, le=20)):
    """Global search across invoices, companies, lenders, and delivery proofs."""
    q = (q or "").strip()
    if not q:
        return {"query": q, "results": []}

    invoices_df = data_store.get("invoices")
    companies_df = data_store.get("companies")
    lenders_df = data_store.get("lenders")
    eway_df = data_store.get("eway_bills")

    results: list[dict[str, Any]] = []

    if not invoices_df.empty:
        matches = invoices_df[invoices_df["invoice_id"].astype(str).str.contains(q, case=False, na=False)]
        for _, row in matches.head(limit).iterrows():
            invoice_id = _clean_text(row.get("invoice_id"))
            seller_name = _clean_text(row.get("seller_id"))
            if "seller_id" in row and not seller_name:
                seller_name = invoice_id
            results.append({
                "id": invoice_id,
                "label": invoice_id,
                "type": "INVOICES",
                "subtitle": f"Invoice • {seller_name}",
                "route": f"/investigation/{invoice_id}",
            })

    if not companies_df.empty:
        company_matches = companies_df[
            companies_df["company_id"].astype(str).str.contains(q, case=False, na=False)
            | companies_df["company_name"].astype(str).str.contains(q, case=False, na=False)
            | companies_df["gstin"].astype(str).str.contains(q, case=False, na=False)
        ]
        for _, row in company_matches.head(limit).iterrows():
            company_id = _clean_text(row.get("company_id"))
            company_name = _clean_text(row.get("company_name"))
            results.append({
                "id": company_id,
                "label": company_name or company_id,
                "type": "COMPANIES",
                "subtitle": f"Company • GSTIN {row.get('gstin', '')}",
                "route": "/invoices",
            })

    if not lenders_df.empty:
        lender_matches = lenders_df[
            lenders_df["lender_id"].astype(str).str.contains(q, case=False, na=False)
            | lenders_df["lender_name"].astype(str).str.contains(q, case=False, na=False)
        ]
        for _, row in lender_matches.head(limit).iterrows():
            lender_id = _clean_text(row.get("lender_id"))
            lender_name = _clean_text(row.get("lender_name"))
            results.append({
                "id": lender_id,
                "label": lender_name or lender_id,
                "type": "LENDERS",
                "subtitle": f"Lender • {lender_id}",
                "route": "/risk",
            })

    if not eway_df.empty:
        eway_matches = eway_df[
            eway_df["eway_bill_no"].astype(str).str.contains(q, case=False, na=False)
            | eway_df["seller_gstin"].astype(str).str.contains(q, case=False, na=False)
            | eway_df["buyer_gstin"].astype(str).str.contains(q, case=False, na=False)
        ]
        for _, row in eway_matches.head(limit).iterrows():
            eway_id = _clean_text(row.get("eway_bill_no"))
            invoice_id = _clean_text(row.get("invoice_id"))
            results.append({
                "id": eway_id,
                "label": eway_id,
                "type": "DELIVERY PROOFS",
                "subtitle": f"Delivery Proof • {invoice_id}",
                "route": f"/investigation/{invoice_id}" if invoice_id else "/graph",
            })

    unique: dict[str, dict[str, Any]] = {}
    for item in results:
        unique.setdefault(item["id"] + item["type"], item)
    final_results = list(unique.values())[: limit]
    return {"query": q, "results": final_results}


@router.get("/alerts")
async def get_alerts():
    invoices_df = data_store.get("invoices")
    risk_df = data_store.get("risk_features")
    companies_df = data_store.get("companies")

    if risk_df.empty:
        return []

    rows = []
    for _, row in risk_df.iterrows():
        invoice_id = _clean_text(row.get("invoice_id"))
        if not invoice_id:
            continue
        level = _clean_text(row.get("risk_level")).upper()
        if level not in {"HIGH", "CRITICAL", "MEDIUM"}:
            continue
        patient = invoices_df.loc[invoice_id] if invoice_id in invoices_df.index else None
        seller_id = patient.get("seller_id", "") if patient is not None else ""
        company_name = seller_id
        if not companies_df.empty and seller_id in companies_df.index:
            company_row = companies_df.loc[seller_id]
            if hasattr(company_row, "iloc") and len(company_row.shape) > 1:
                company_row = company_row.iloc[0]
            company_name = _clean_text(company_row.get("company_name", seller_id))
        rows.append({
            "invoice_id": invoice_id,
            "level": level,
            "risk_score": int(row.get("risk_score", 0)),
            "title": f"{level} risk alert — {invoice_id}",
            "message": (
                f"{company_name} invoice has an elevated risk classification with {level.lower()} priority review."
                if company_name else f"Invoice {invoice_id} requires review due to a {level.lower()} risk classification."
            ),
            "route": f"/investigation/{invoice_id}",
            "timestamp": _clean_text(row.get("risk_timestamp", "Date unavailable")) or "Date unavailable",
        })

    rows.sort(key=lambda x: x["risk_score"], reverse=True)
    return rows[:25]


@router.get("/invoices/{invoice_id}/timeline")
async def get_invoice_timeline(invoice_id: str):
    detail = _build_detail(invoice_id)
    risk = run_verification(invoice_id)
    events = [
        {"date": detail.invoice_date or "Date unavailable", "label": "Invoice Created", "detail": f"Invoice {detail.invoice_id} entered the ledger.", "severity": "info"},
    ]
    for financing in detail.financing_records:
        date = financing.application_date or "Date unavailable"
        events.append({
            "date": date,
            "label": f"{financing.lender_id} Financing",
            "detail": f"{financing.lender_name} financed ₹{financing.financed_amount:,.0f}.",
            "severity": "warning" if financing.financed_amount > 0 else "info",
        })
    if detail.eway_bill and detail.eway_bill.movement_date:
        events.append({
            "date": detail.eway_bill.movement_date,
            "label": "Delivery Proof Recorded",
            "detail": f"E-Way bill {detail.eway_bill.eway_bill_no} movement logged.",
            "severity": "info",
        })
    events.append({
        "date": risk.audit_trail[-1].timestamp if risk.audit_trail else "Date unavailable",
        "label": "Risk Detected",
        "detail": risk.summary,
        "severity": "warning" if risk.risk_level in {"HIGH", "CRITICAL"} else "info",
    })
    events.append({
        "date": "Date unavailable",
        "label": "Review Required",
        "detail": f"Recommended action: {risk.recommended_action}.",
        "severity": "warning",
    })
    return {"invoice_id": invoice_id, "events": events}


@router.get("/invoices/{invoice_id}/evidence")
async def get_invoice_evidence(invoice_id: str):
    risk = run_verification(invoice_id)
    return {"invoice_id": invoice_id, "evidence": [item.model_dump() for item in risk.evidence]}


@router.get("/investigation/{invoice_id}")
async def get_investigation(invoice_id: str):
    try:
        invoice = _build_detail(invoice_id)
        risk = run_verification(invoice_id)
        graph = build_invoice_graph(invoice_id)
        timeline = (await get_invoice_timeline(invoice_id))
        evidence = (await get_invoice_evidence(invoice_id))
        return {
            "invoice_id": invoice.invoice_id,
            "invoice": invoice.model_dump(),
            "risk": risk.model_dump(),
            "graph": graph.model_dump(),
            "timeline": timeline["events"],
            "evidence": evidence["evidence"],
            "status": "REVIEW REQUIRED" if risk.risk_level in {"HIGH", "CRITICAL"} else "MONITOR",
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
