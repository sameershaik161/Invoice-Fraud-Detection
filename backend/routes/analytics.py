"""Lenders and analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from typing import List
from schemas.schemas import LenderSchema, OverviewSchema, AnalyticsSchema
from services.analytics_service import get_overview, get_analytics
import data_store

router = APIRouter(tags=["Analytics"])


@router.get("/lenders", response_model=List[LenderSchema])
async def list_lenders():
    lenders_df = data_store.get("lenders")
    financing_df = data_store.get("financing")
    risk_df = data_store.get("risk_features")
    fraud_df = data_store.get("fraud_labels")

    if lenders_df.empty:
        return []

    results = []
    for _, row in lenders_df.iterrows():
        lid = str(row.get("lender_id", ""))
        lname = str(row.get("lender_name", ""))
        ltype = str(row.get("lender_type", ""))

        total_inv = 0
        total_exp = 0.0
        high_risk = 0
        dup_attempts = 0

        if not financing_df.empty:
            lf = financing_df[financing_df["lender_id"] == lid]
            total_inv = len(lf)
            total_exp = float(lf["financed_amount"].sum())
            inv_ids = lf["invoice_id"].tolist()

            if not risk_df.empty:
                lf_risk = risk_df[risk_df["invoice_id"].isin(inv_ids)]
                high_risk = int(lf_risk["risk_level"].isin(["HIGH", "CRITICAL"]).sum())

            if not fraud_df.empty:
                lf_fraud = fraud_df[fraud_df["invoice_id"].isin(inv_ids)]
                dup_attempts = int((lf_fraud["ground_truth_label"] == "DOUBLE_FINANCING").sum())

        results.append(LenderSchema(
            lender_id=lid,
            lender_name=lname,
            lender_type=ltype,
            total_invoices=total_inv,
            total_exposure=total_exp,
            high_risk_count=high_risk,
            duplicate_attempts=dup_attempts,
        ))

    return results


@router.get("/analytics/overview", response_model=OverviewSchema)
async def overview():
    return get_overview()


@router.get("/analytics/charts", response_model=AnalyticsSchema)
async def analytics_charts():
    return get_analytics()


@router.get("/sec/filings/{company_id}", tags=["SEC EDGAR"])
async def get_sec_filings(company_id: str):
    """Retrieve simulated SEC EDGAR 10-K/10-Q corporate disclosures and lien notes for a company."""
    from services.sec_edgar_service import lookup_sec_filings
    return lookup_sec_filings(company_id)
