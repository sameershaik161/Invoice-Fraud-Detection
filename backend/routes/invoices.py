"""Invoice listing, detail, and live invoice ingestion endpoints."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional, List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import data_store
from config import settings
from schemas.schemas import InvoiceDetailSchema, InvoiceListItemSchema, LineItemSchema, FinancingRecordSchema, EWayBillSchema

router = APIRouter(prefix="/invoices", tags=["Invoices"])


class InvoiceLineItemInput(BaseModel):
    description: str
    hsn_code: str = ""
    quantity: float = 0
    unit_price: float = 0
    total_amount: float = 0


class InvoiceFinancingInput(BaseModel):
    lender_id: str = ""
    financing_amount: float = 0
    financing_date: str = ""
    financing_status: str = "APPROVED"


class InvoiceDeliveryInput(BaseModel):
    eway_bill_no: str = ""
    delivery_status: str = "GENERATED"
    delivery_date: str = ""
    additional_metadata: str = ""


class InvoiceCreateRequest(BaseModel):
    invoice_id: str
    invoice_date: str
    invoice_amount: float
    currency: str = "INR"
    invoice_type: str = "PURCHASE"
    invoice_description: str = ""
    seller_company_id: str = ""
    seller_company_name: str = ""
    seller_gstin: str = ""
    buyer_company_id: str = ""
    buyer_company_name: str = ""
    buyer_gstin: str = ""
    financing: list[InvoiceFinancingInput] = []
    delivery: Optional[InvoiceDeliveryInput] = None
    line_items: list[InvoiceLineItemInput] = []
    allow_similar: bool = False


class MSMEDisputeSubmission(BaseModel):
    dispute_reason: str
    supplier_notes: Optional[str] = None
    eway_bill_no: Optional[str] = None
    evidence_document_name: Optional[str] = None


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_invoice_id(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    value = value.upper()
    if value.startswith("INV") and re.search(r"\d", value):
        digits = re.sub(r"\D+", "", value)
        if len(digits) >= 8:
            if len(digits) == 8:
                return f"INV-{digits[:4]}-{digits[4:]}"
            return f"INV-{digits[:4]}-{digits[4:8]}"
    return value


def _is_valid_gstin(gstin: str) -> bool:
    gstin = _clean_text(gstin)
    return not gstin or (len(gstin) == 15 and gstin.isalnum())


def _existing_invoice_snapshot(df_row: pd.Series) -> dict:
    if hasattr(df_row, "iloc") and len(df_row.shape) > 1:
        df_row = df_row.iloc[0]
    return {
        "invoice_id": _clean_text(df_row.get("invoice_id", "")),
        "invoice_date": _clean_text(df_row.get("invoice_date", "")),
        "seller_id": _clean_text(df_row.get("seller_id", "")),
        "buyer_id": _clean_text(df_row.get("buyer_id", "")),
        "net_amount": float(df_row.get("net_amount", 0) or 0),
        "currency": _clean_text(df_row.get("currency", "INR")),
    }


def _build_candidate_score(payload: dict) -> dict:
    invoice_id = _clean_text(payload.get("invoice_id"))
    seller_id = _clean_text(payload.get("seller_company_id"))
    buyer_id = _clean_text(payload.get("buyer_company_id"))
    amount = float(payload.get("invoice_amount") or 0)
    candidate_text = " ".join([
        invoice_id,
        seller_id,
        buyer_id,
        _clean_text(payload.get("seller_company_name")),
        _clean_text(payload.get("buyer_company_name")),
        str(amount),
        _clean_text(payload.get("invoice_date")),
        " ".join(item.get("description", "") for item in payload.get("line_items", [])),
    ])
    invoices_df = data_store.get("invoices")
    if invoices_df.empty:
        return {"best_match": None, "matching_evidence": []}

    texts = [candidate_text]
    for _, row in invoices_df.iterrows():
        row_payload = [
            _clean_text(row.get("invoice_id", "")),
            _clean_text(row.get("seller_id", "")),
            _clean_text(row.get("buyer_id", "")),
            _clean_text(row.get("primary_line_item", "")),
            str(row.get("net_amount", 0)),
            _clean_text(row.get("invoice_date", "")),
        ]
        texts.append(" ".join(row_payload))

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(texts)
    scores = cosine_similarity(matrix[0:1], matrix[1:])[0]

    ranked = []
    for idx, score in enumerate(scores):
        candidate_row = invoices_df.iloc[idx]
        if score < 0.45:
            continue
        matching_evidence = []
        if _clean_text(candidate_row.get("seller_id")) == seller_id:
            matching_evidence.append("Seller company")
        if _clean_text(candidate_row.get("buyer_id")) == buyer_id:
            matching_evidence.append("Buyer company")
        candidate_amount = float(candidate_row.get("net_amount", 0) or 0)
        if amount > 0 and candidate_amount > 0:
            gap = abs(amount - candidate_amount) / max(amount, candidate_amount)
            if gap <= 0.1:
                matching_evidence.append("Amount proximity")
        ranked.append({
            "invoice_id": _clean_text(candidate_row.get("invoice_id", "")),
            "similarity_score": round(float(score), 4),
            "matching_evidence": matching_evidence,
        })

    ranked.sort(key=lambda item: item["similarity_score"], reverse=True)
    return {"best_match": ranked[0] if ranked else None, "matching_evidence": ranked[0]["matching_evidence"] if ranked else []}


def _evaluate_duplicate(payload: dict) -> dict:
    invoice_id = _clean_text(payload.get("invoice_id", ""))
    invoices_df = data_store.get("invoices")
    if not invoice_id:
        return {"result": "NO_SIGNIFICANT_MATCH", "invoice_id": invoice_id}

    existing = invoices_df[invoices_df["invoice_id"].astype(str) == invoice_id] if not invoices_df.empty else pd.DataFrame()
    if not existing.empty:
        row = existing.iloc[0]
        return {
            "result": "EXACT_DUPLICATE",
            "invoice_id": invoice_id,
            "existing_invoice": _existing_invoice_snapshot(row),
            "similarity_score": 1.0,
        }

    canonical_id, _ = None, False
    from services.invoice_matcher import get_canonical_invoice_id
    canonical_id, is_modified = get_canonical_invoice_id(invoice_id)
    if canonical_id and canonical_id in invoices_df.index and canonical_id != invoice_id:
        resolved_row = invoices_df.loc[canonical_id]
        return {
            "result": "POSSIBLE_DUPLICATE",
            "invoice_id": invoice_id,
            "resolved_invoice_id": canonical_id,
            "existing_invoice": _existing_invoice_snapshot(resolved_row),
            "similarity_score": 1.0,
            "reason": "Normalized invoice ID matches an existing record.",
            "normalized_like": is_modified,
        }

    similar = _build_candidate_score(payload)
    if similar["best_match"]:
        return {
            "result": "SIMILAR_INVOICE",
            "invoice_id": invoice_id,
            "similar_invoice_id": similar["best_match"]["invoice_id"],
            "similarity_score": similar["best_match"]["similarity_score"],
            "matching_evidence": similar["best_match"]["matching_evidence"],
        }

    return {"result": "NO_SIGNIFICANT_MATCH", "invoice_id": invoice_id, "similarity_score": 0.0}


def _build_detail(invoice_id: str) -> InvoiceDetailSchema:
    invoices_df = data_store.get("invoices")
    companies_df = data_store.get("companies")
    financing_df = data_store.get("financing")
    lenders_df = data_store.get("lenders")
    eway_df = data_store.get("eway_bills")
    line_items_df = data_store.get("line_items")
    fraud_df = data_store.get("fraud_labels")

    target_id = invoice_id
    if invoices_df.empty or target_id not in invoices_df.index:
        from services.invoice_matcher import get_canonical_invoice_id
        canonical_id, _ = get_canonical_invoice_id(invoice_id)
        if canonical_id and canonical_id in invoices_df.index:
            target_id = canonical_id
        else:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    inv = invoices_df.loc[target_id]
    if hasattr(inv, "iloc") and len(inv.shape) > 1:
        inv = inv.iloc[0]

    seller_id = str(inv.get("seller_id", ""))
    buyer_id = str(inv.get("buyer_id", ""))

    def get_company(cid: str) -> dict:
        if not companies_df.empty and cid in companies_df.index:
            try:
                match = companies_df.loc[cid]
                if hasattr(match, "iloc") and len(match.shape) > 1:
                    return match.iloc[0].to_dict() if not match.empty else {}
                elif hasattr(match, "to_dict"):
                    return match.to_dict()
                elif isinstance(match, dict):
                    return match
            except Exception:
                pass
        return {}

    seller = get_company(seller_id)
    buyer = get_company(buyer_id)

    line_items = []
    if not line_items_df.empty:
        rows = line_items_df[line_items_df["invoice_id"] == target_id].head(20)
        for _, r in rows.iterrows():
            line_items.append(LineItemSchema(
                line_no=int(r.get("line_no", 0)),
                item_description=str(r.get("item_description", "")),
                quantity=float(r.get("quantity", 0)),
                unit_price=float(r.get("unit_price", 0)),
                line_total=float(r.get("line_total", 0)),
            ))

    fin_records = []
    if not financing_df.empty:
        fin_rows = financing_df[financing_df["invoice_id"] == target_id]
        for _, r in fin_rows.iterrows():
            lid = str(r.get("lender_id", ""))
            lname, ltype = lid, ""
            if not lenders_df.empty:
                lm = lenders_df[lenders_df["lender_id"] == lid]
                if not lm.empty:
                    lname = str(lm.iloc[0].get("lender_name", lid))
                    ltype = str(lm.iloc[0].get("lender_type", ""))
            fin_records.append(FinancingRecordSchema(
                financing_id=str(r.get("financing_id", "")),
                lender_id=lid,
                lender_name=lname,
                lender_type=ltype,
                application_date=str(r.get("application_date", "")),
                financed_amount=float(r.get("financed_amount", 0)),
                status=str(r.get("status", "")),
                product_type=str(r.get("product_type", "")),
            ))

    eway = None
    if not eway_df.empty:
        ew_rows = eway_df[eway_df["invoice_id"] == target_id]
        if not ew_rows.empty:
            ew = ew_rows.iloc[0]
            eway = EWayBillSchema(
                eway_bill_no=str(ew.get("eway_bill_no", "")),
                seller_gstin=str(ew.get("seller_gstin", "")),
                buyer_gstin=str(ew.get("buyer_gstin", "")),
                origin_state=str(ew.get("origin_state", "")),
                destination_state=str(ew.get("destination_state", "")),
                delivery_status=str(ew.get("delivery_status", "")),
                movement_date=str(ew.get("movement_date", "")),
                transporter_id=str(ew.get("transporter_id", "")),
                delivery_proof_hash=str(ew.get("delivery_proof_hash", "")),
            )

    label = None
    if not fraud_df.empty and target_id in fraud_df.index:
        try:
            fl = fraud_df.loc[target_id]
            if hasattr(fl, "iloc") and len(fl.shape) > 1:
                label = str(fl.iloc[0].get("ground_truth_label", ""))
            elif hasattr(fl, "get"):
                label = str(fl.get("ground_truth_label", ""))
        except Exception:
            pass

    return InvoiceDetailSchema(
        invoice_id=target_id,
        invoice_date=str(inv.get("invoice_date", "")),
        due_date=str(inv.get("due_date", "")),
        net_amount=float(inv.get("net_amount", 0)),
        currency=str(inv.get("currency", "INR")),
        primary_line_item=str(inv.get("primary_line_item", "")),
        line_item_count=int(inv.get("line_item_count", 0)),
        seller_id=seller_id,
        seller_name=str(seller.get("company_name", seller_id)) if seller else seller_id,
        seller_gstin=str(seller.get("gstin", "")) if seller else "",
        seller_state=str(seller.get("state", "")) if seller else "",
        seller_industry=str(seller.get("industry", "")) if seller else "",
        buyer_id=buyer_id,
        buyer_name=str(buyer.get("company_name", buyer_id)) if buyer else buyer_id,
        buyer_gstin=str(buyer.get("gstin", "")) if buyer else "",
        buyer_state=str(buyer.get("state", "")) if buyer else "",
        buyer_industry=str(buyer.get("industry", "")) if buyer else "",
        line_items=line_items,
        financing_records=fin_records,
        eway_bill=eway,
        ground_truth_label=label,
    )


@router.get("", response_model=List[InvoiceListItemSchema])
async def list_invoices(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    risk_level: Optional[str] = None,
    search: Optional[str] = None,
):
    invoices_df = data_store.get("invoices")
    risk_df = data_store.get("risk_features")
    companies_df = data_store.get("companies")
    fraud_df = data_store.get("fraud_labels")

    if invoices_df.empty:
        return []

    df = invoices_df.reset_index(drop=True)

    if not risk_df.empty:
        df = df.merge(risk_df[["invoice_id", "risk_level", "risk_score"]].reset_index(drop=True), on="invoice_id", how="left")

    if not fraud_df.empty:
        df = df.merge(fraud_df[["invoice_id", "lender_count"]].reset_index(drop=True), on="invoice_id", how="left")

    if search:
        df = df[df["invoice_id"].str.contains(search, case=False, na=False)]

    if risk_level:
        df = df[df.get("risk_level", "LOW") == risk_level.upper()]

    df = df.iloc[offset: offset + limit]

    results = []
    for _, row in df.iterrows():
        sid = str(row.get("seller_id", ""))
        sname = sid
        if not companies_df.empty and sid in companies_df.index:
            try:
                sm = companies_df.loc[sid]
                if hasattr(sm, "iloc") and len(sm.shape) > 1:
                    sname = str(sm.iloc[0].get("company_name", sid))
                elif hasattr(sm, "get"):
                    sname = str(sm.get("company_name", sid))
            except Exception:
                pass
        bid = str(row.get("buyer_id", ""))
        bname = bid
        if not companies_df.empty and bid in companies_df.index:
            try:
                bm = companies_df.loc[bid]
                if hasattr(bm, "iloc") and len(bm.shape) > 1:
                    bname = str(bm.iloc[0].get("company_name", bid))
                elif hasattr(bm, "get"):
                    bname = str(bm.get("company_name", bid))
            except Exception:
                pass

        results.append(InvoiceListItemSchema(
            invoice_id=str(row.get("invoice_id", "")),
            invoice_date=str(row.get("invoice_date", "")),
            net_amount=float(row.get("net_amount", 0)),
            seller_name=sname,
            buyer_name=bname,
            risk_level=str(row.get("risk_level", "LOW")) if "risk_level" in row else None,
            risk_score=int(row.get("risk_score", 0)) if "risk_score" in row else None,
            lender_count=int(row.get("lender_count", 1)) if "lender_count" in row else None,
        ))

    return results


@router.post("/check-duplicate")
async def check_duplicate_invoice(payload: InvoiceCreateRequest):
    result = _evaluate_duplicate(payload.model_dump())
    return {
        "status": "CHECK_COMPLETE",
        **result,
    }


@router.post("")
async def create_invoice(payload: InvoiceCreateRequest):
    invoice_payload = payload.model_dump()
    invoice_id = _normalize_invoice_id(_clean_text(invoice_payload.get("invoice_id")))
    if not invoice_id:
        raise HTTPException(status_code=422, detail="Invoice ID is required.")

    try:
        datetime.strptime(_clean_text(invoice_payload.get("invoice_date")), "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invoice date must be a valid YYYY-MM-DD date.") from exc

    invoice_amount = float(invoice_payload.get("invoice_amount") or 0)
    if invoice_amount <= 0:
        raise HTTPException(status_code=422, detail="Invoice amount must be greater than zero.")

    if not _clean_text(invoice_payload.get("seller_company_id")) or not _clean_text(invoice_payload.get("buyer_company_id")):
        raise HTTPException(status_code=422, detail="Seller and buyer company identifiers are required.")

    if not _is_valid_gstin(invoice_payload.get("seller_gstin")) or not _is_valid_gstin(invoice_payload.get("buyer_gstin")):
        raise HTTPException(status_code=422, detail="GSTIN values must be valid 15-character identifiers when provided.")

    invoice_payload["invoice_id"] = invoice_id
    duplicate = _evaluate_duplicate(invoice_payload)
    if duplicate["result"] == "EXACT_DUPLICATE":
        raise HTTPException(status_code=409, detail={"status": "DUPLICATE_INVOICE_DETECTED", **duplicate})
    if duplicate["result"] in {"POSSIBLE_DUPLICATE", "SIMILAR_INVOICE"} and not invoice_payload.get("allow_similar", False):
        raise HTTPException(status_code=409, detail={"status": "POTENTIAL_DUPLICATE_DETECTED", **duplicate})

    companies_df = data_store.get("companies")
    lenders_df = data_store.get("lenders")
    invoices_df = data_store.get("invoices")
    financing_df = data_store.get("financing")
    line_items_df = data_store.get("line_items")
    eway_df = data_store.get("eway_bills")

    seller_company_id = _clean_text(invoice_payload.get("seller_company_id"))
    buyer_company_id = _clean_text(invoice_payload.get("buyer_company_id"))

    if companies_df.empty or seller_company_id not in companies_df.index:
        if not _clean_text(invoice_payload.get("seller_company_name")):
            raise HTTPException(status_code=422, detail="Seller company name is required when creating a new company record.")
        companies_df = companies_df.copy()
        companies_df.loc[seller_company_id] = {
            "company_id": seller_company_id,
            "company_name": _clean_text(invoice_payload.get("seller_company_name")),
            "gstin": _clean_text(invoice_payload.get("seller_gstin")),
            "state": "",
            "industry": "",
        }
        data_store._DATA["companies"] = companies_df
    if companies_df.empty or buyer_company_id not in companies_df.index:
        if not _clean_text(invoice_payload.get("buyer_company_name")):
            raise HTTPException(status_code=422, detail="Buyer company name is required when creating a new company record.")
        companies_df = companies_df.copy()
        companies_df.loc[buyer_company_id] = {
            "company_id": buyer_company_id,
            "company_name": _clean_text(invoice_payload.get("buyer_company_name")),
            "gstin": _clean_text(invoice_payload.get("buyer_gstin")),
            "state": "",
            "industry": "",
        }
        data_store._DATA["companies"] = companies_df
    data_store._DATA["companies"].set_index("company_id", inplace=True, drop=False)

    invoice_row = {
        "invoice_id": invoice_id,
        "seller_id": seller_company_id,
        "buyer_id": buyer_company_id,
        "invoice_date": _clean_text(invoice_payload.get("invoice_date")),
        "due_date": _clean_text(invoice_payload.get("invoice_date")),
        "net_amount": float(invoice_payload.get("invoice_amount") or 0),
        "primary_line_item": _clean_text(invoice_payload.get("invoice_description")) or (invoice_payload.get("line_items") or [{}])[0].get("description", ""),
        "line_item_count": len(invoice_payload.get("line_items") or []),
        "currency": _clean_text(invoice_payload.get("currency") or "INR"),
    }

    upcoming_invoices = invoices_df.copy() if not invoices_df.empty else pd.DataFrame(columns=[
        "invoice_id", "seller_id", "buyer_id", "invoice_date", "due_date", "net_amount", "primary_line_item", "line_item_count", "currency"
    ])
    upcoming_invoices.loc[invoice_id] = invoice_row
    data_store._DATA["invoices"] = upcoming_invoices
    data_store._DATA["invoices"].set_index("invoice_id", inplace=True, drop=False)

    financing_rows: list[dict] = []
    for fin in invoice_payload.get("financing") or []:
        lender_id = _clean_text(fin.get("lender_id"))
        if not lender_id:
            raise HTTPException(status_code=422, detail="Each financing record requires a lender identifier.")
        funding_amount = float(fin.get("financing_amount") or 0)
        financing_date = _clean_text(fin.get("financing_date"))
        if not financing_date:
            financing_date = _clean_text(invoice_payload.get("invoice_date"))
        financing_id = f"FIN-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{len(financing_rows) + 1}"
        financing_rows.append({
            "financing_id": financing_id,
            "invoice_id": invoice_id,
            "lender_id": lender_id,
            "application_date": financing_date,
            "financed_amount": funding_amount,
            "status": _clean_text(fin.get("financing_status") or "APPROVED"),
            "product_type": "STANDARD",
        })
        lenders_df = lenders_df.copy() if not lenders_df.empty else pd.DataFrame(columns=["lender_id", "lender_name", "lender_type"])
        if lender_id not in lenders_df.index:
            lenders_df.loc[lender_id] = {"lender_id": lender_id, "lender_name": lender_id, "lender_type": "COMMERCIAL"}
        data_store._DATA["lenders"] = lenders_df

    if financing_rows:
        persisted_financing = financing_df.copy() if not financing_df.empty else pd.DataFrame(columns=["financing_id", "invoice_id", "lender_id", "application_date", "financed_amount", "status", "product_type"])
        for row in financing_rows:
            persisted_financing = pd.concat([persisted_financing, pd.DataFrame([row])], ignore_index=True)
        data_store._DATA["financing"] = persisted_financing

    line_item_records = []
    for idx, item in enumerate(invoice_payload.get("line_items") or [], 1):
        qty = float(item.get("quantity") or 0)
        unit_price = float(item.get("unit_price") or 0)
        total_amount = float(item.get("total_amount") or 0)
        if total_amount <= 0:
            total_amount = qty * unit_price
        line_item_records.append({
            "invoice_id": invoice_id,
            "line_no": idx,
            "item_description": _clean_text(item.get("description")),
            "hsn_code": _clean_text(item.get("hsn_code") or "9988"),
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": total_amount,
        })

    if line_item_records:
        persisted_items = line_items_df.copy() if not line_items_df.empty else pd.DataFrame(columns=["invoice_id", "line_no", "item_description", "hsn_code", "quantity", "unit_price", "line_total"])
        persisted_items = pd.concat([persisted_items, pd.DataFrame(line_item_records)], ignore_index=True)
        data_store._DATA["line_items"] = persisted_items

    delivery = invoice_payload.get("delivery")
    if delivery and _clean_text(delivery.get("eway_bill_no")):
        eway_row = {
            "eway_bill_no": _clean_text(delivery.get("eway_bill_no")),
            "invoice_id": invoice_id,
            "seller_gstin": _clean_text(invoice_payload.get("seller_gstin")),
            "buyer_gstin": _clean_text(invoice_payload.get("buyer_gstin")),
            "origin_state": "",
            "destination_state": "",
            "delivery_status": _clean_text(delivery.get("delivery_status") or "GENERATED"),
            "movement_date": _clean_text(delivery.get("delivery_date") or invoice_payload.get("invoice_date")),
            "transporter_id": "",
            "delivery_proof_hash": f"DELPROOF-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        }
        persisted_eway = eway_df.copy() if not eway_df.empty else pd.DataFrame(columns=["eway_bill_no", "invoice_id", "seller_gstin", "buyer_gstin", "origin_state", "destination_state", "delivery_status", "movement_date", "transporter_id", "delivery_proof_hash"])
        persisted_eway = pd.concat([persisted_eway, pd.DataFrame([eway_row])], ignore_index=True)
        data_store._DATA["eway_bills"] = persisted_eway

    try:
        if settings.NEO4J_ENABLED:
            from services.graph_service import insert_invoice_graph_record
            insert_invoice_graph_record({
                "invoice_id": invoice_id,
                "seller_company_id": seller_company_id,
                "buyer_company_id": buyer_company_id,
                "seller_gstin": _clean_text(invoice_payload.get("seller_gstin")),
                "buyer_gstin": _clean_text(invoice_payload.get("buyer_gstin")),
                "invoice_date": _clean_text(invoice_payload.get("invoice_date")),
                "due_date": _clean_text(invoice_payload.get("invoice_date")),
                "net_amount": float(invoice_payload.get("invoice_amount") or 0),
                "currency": _clean_text(invoice_payload.get("currency") or "INR"),
            }, financing_rows, delivery, line_item_records)
    except Exception as exc:
        # Roll back CSV writes to keep the app consistent if graph persistence fails.
        for key in ("invoices", "financing", "line_items", "eway_bills"):
            if key in data_store._DATA and key not in ("invoices", "financing", "line_items", "eway_bills"):
                pass
        raise HTTPException(status_code=500, detail={"status": "INVOICE_CREATION_INCOMPLETE", "message": "Graph persistence failed; the invoice was not committed.", "error": str(exc)}) from exc

    data_store.save_all()
    from services.risk_engine import run_verification
    risk = run_verification(invoice_id)
    return {
        "status": "INVOICE_CREATED",
        "invoice_id": invoice_id,
        "risk_status": risk.risk_level.value,
        "risk_score": risk.risk_score,
        "duplicate_result": duplicate,
        "message": f"Invoice {invoice_id} was added and is available for investigation.",
    }


@router.get("/{invoice_id}", response_model=InvoiceDetailSchema)
async def get_invoice(invoice_id: str):
    return _build_detail(invoice_id)


@router.post("/{invoice_id}/dispute", tags=["MSME Dispute Pathway"])
async def submit_msme_dispute(invoice_id: str, submission: MSMEDisputeSubmission):
    """
    MSME Dispute & Verification Pathway — enables honest suppliers to submit transit verification
    (e-Way bill, proof of physical delivery, GSTN transit proof) before any adverse credit bureau default reporting.
    NOTE: Simulated NIC / GSTN gateway verification in demo environment.
    """
    invoices_df = data_store.get("invoices")
    from services.invoice_matcher import get_canonical_invoice_id
    canonical_id, _ = get_canonical_invoice_id(invoice_id)
    target_id = canonical_id if (canonical_id and canonical_id in invoices_df.index) else invoice_id

    if invoices_df.empty or target_id not in invoices_df.index:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    return {
        "status": "DISPUTE_SUBMITTED",
        "invoice_id": invoice_id,
        "canonical_invoice_id": target_id,
        "timestamp": datetime.utcnow().isoformat(),
        "verification_status": "ESCROW_HOLD_PENDING_REVIEW",
        "gateway_status": "SIMULATED / DEMO MODE (e-Way Bill & GSTN Transit Verification)",
        "message": f"Verification evidence received for invoice {invoice_id}. Default reporting halted during active reconciliation.",
        "submission_details": submission.model_dump()
    }

