"""
SEC EDGAR Service — Adapter for Corporate Financial Disclosures.
STATUS: SIMULATED / DEMO CORPUS (SEC EDGAR Form 10-K / 10-Q Filings)
Provides corporate filings, known liens, and factoring credit facility cross-checks.
"""
from __future__ import annotations

import data_store
from typing import Optional, List
from pydantic import BaseModel


class SECFilingSchema(BaseModel):
    company_id: str
    company_name: str
    cik: str
    form_type: str  # "10-K" | "10-Q" | "8-K"
    filing_date: str
    fiscal_period: str
    accounts_receivable_disclosed: float
    credit_facilities_disclosed: List[str]
    lien_encumbrance_notes: str
    status: str  # "SIMULATED / DEMO CORPUS"


def lookup_sec_filings(company_id: str) -> dict:
    """
    Looks up SEC corporate filing disclosure records for a company.
    Cross-checks whether receivables or floating charges have been publicly disclosed.
    """
    companies_df = data_store.get("companies")
    company_name = company_id
    industry = "Manufacturing"
    if not companies_df.empty and company_id in companies_df.index:
        c_row = companies_df.loc[company_id]
        if hasattr(c_row, "iloc") and len(c_row.shape) > 1:
            c_row = c_row.iloc[0]
        company_name = str(c_row.get("company_name", company_id))
        industry = str(c_row.get("industry", "Manufacturing"))

    # Deterministic synthetic CIK based on hash of company_id
    cik_num = abs(hash(company_id)) % 9000000 + 1000000
    cik = f"{cik_num:010d}"

    filings = [
        SECFilingSchema(
            company_id=company_id,
            company_name=company_name,
            cik=cik,
            form_type="10-K",
            filing_date="2025-12-31",
            fiscal_period="FY2025",
            accounts_receivable_disclosed=45_000_000.0,
            credit_facilities_disclosed=[
                "Working Capital Facility — State Bank Syndicate",
                "Receivable Factoring Facility — Non-Exclusive Subordinated Lien"
            ],
            lien_encumbrance_notes=(
                f"Note 7 (Borrowings and Pledged Assets): {company_name} maintains revolving receivables "
                "pledges. Subordinated encumbrances permitted subject to senior inter-creditor parity."
            ),
            status="SIMULATED / DEMO CORPUS"
        ),
        SECFilingSchema(
            company_id=company_id,
            company_name=company_name,
            cik=cik,
            form_type="10-Q",
            filing_date="2026-03-31",
            fiscal_period="Q1 2026",
            accounts_receivable_disclosed=52_500_000.0,
            credit_facilities_disclosed=[
                "Supply Chain Financing Program — Registered Secured Notes"
            ],
            lien_encumbrance_notes=(
                "Item 2: Disclosed active supply chain factoring facilities across registered lending partners."
            ),
            status="SIMULATED / DEMO CORPUS"
        )
    ]

    return {
        "company_id": company_id,
        "company_name": company_name,
        "cik": cik,
        "industry": industry,
        "filings": [f.model_dump() for f in filings],
        "adapter_mode": "SIMULATED / DEMO CORPUS",
        "notes": "SEC EDGAR filing ingestion adapter provided for hackathon judging environment without live SEC EDGAR API keys."
    }
