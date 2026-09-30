"""
Analytics service — computes dashboard KPIs and chart data from in-memory CSV data.
"""
from __future__ import annotations

import data_store
from schemas.schemas import OverviewSchema, AnalyticsSchema


def get_overview() -> OverviewSchema:
    invoices_df = data_store.get("invoices")
    fraud_df = data_store.get("fraud_labels")
    financing_df = data_store.get("financing")
    lenders_df = data_store.get("lenders")
    risk_df = data_store.get("risk_features")

    total_invoices = len(invoices_df) if not invoices_df.empty else 0
    lenders_connected = len(lenders_df) if not lenders_df.empty else 0

    high_risk = 0
    critical = 0
    double_financing_count = 0
    potential_exposure = 0.0
    detection_rate = None

    if not fraud_df.empty:
        double_financing_count = int((fraud_df["ground_truth_label"] == "DOUBLE_FINANCING").sum())

    if not risk_df.empty:
        high_risk = int((risk_df["risk_level"].isin(["HIGH", "CRITICAL"])).sum())
        critical = int((risk_df["risk_level"] == "CRITICAL").sum())

    if not financing_df.empty and not invoices_df.empty:
        # Exposure = financing on HIGH-risk invoices
        if not risk_df.empty:
            high_risk_ids = risk_df[risk_df["risk_level"].isin(["HIGH", "CRITICAL"])].index.tolist()
            exposed = financing_df[financing_df["invoice_id"].isin(high_risk_ids)]
            potential_exposure = float(exposed["financed_amount"].sum())

    if not fraud_df.empty and not risk_df.empty:
        labeled = fraud_df[["invoice_id", "ground_truth_label"]].reset_index(drop=True).merge(
            risk_df[["invoice_id", "risk_level"]].reset_index(drop=True), on="invoice_id", how="inner"
        )
        positives = labeled[labeled["ground_truth_label"] == "DOUBLE_FINANCING"]
        if not positives.empty:
            detected = positives[positives["risk_level"].isin(["HIGH", "CRITICAL"])]
            detection_rate = round(len(detected) / len(positives) * 100, 1)

    return OverviewSchema(
        total_invoices=total_invoices,
        verified_today=None,
        high_risk_invoices=high_risk,
        critical_invoices=critical,
        potential_exposure=round(potential_exposure, 0),
        lenders_connected=lenders_connected,
        detection_rate=detection_rate,
        double_financing_count=double_financing_count,
    )


def get_analytics() -> AnalyticsSchema:
    risk_df = data_store.get("risk_features")
    financing_df = data_store.get("financing")
    invoices_df = data_store.get("invoices")
    companies_df = data_store.get("companies")
    lenders_df = data_store.get("lenders")
    fraud_df = data_store.get("fraud_labels")

    # Risk distribution
    risk_dist = []
    if not risk_df.empty:
        for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = int((risk_df["risk_level"] == level).sum())
            risk_dist.append({"level": level, "count": count})

    # Financing by lender
    fin_by_lender = []
    if not financing_df.empty and not lenders_df.empty:
        grouped = financing_df.groupby("lender_id")["financed_amount"].sum().reset_index()
        for _, row in grouped.iterrows():
            lname = row["lender_id"]
            match = lenders_df[lenders_df["lender_id"] == row["lender_id"]]
            if not match.empty:
                lname = match.iloc[0]["lender_name"]
            fin_by_lender.append({"lender": lname, "amount": round(float(row["financed_amount"]) / 1e5, 2)})
        fin_by_lender.sort(key=lambda x: x["amount"], reverse=True)
        fin_by_lender = fin_by_lender[:10]

    # Industry risk
    industry_risk = []
    if not invoices_df.empty and not companies_df.empty and not risk_df.empty:
        merged = invoices_df.reset_index(drop=True).merge(
            companies_df[["company_id", "industry"]].rename(columns={"company_id": "seller_id"}),
            on="seller_id", how="left"
        )
        merged = merged.merge(risk_df[["invoice_id", "risk_score"]].reset_index(drop=True),
                              on="invoice_id", how="left")
        ind_grouped = merged.groupby("industry")["risk_score"].mean().reset_index()
        for _, row in ind_grouped.iterrows():
            if str(row["industry"]) not in ("nan", ""):
                industry_risk.append({
                    "industry": str(row["industry"]),
                    "avg_risk": round(float(row["risk_score"]), 1)
                })
        industry_risk.sort(key=lambda x: x["avg_risk"], reverse=True)
        industry_risk = industry_risk[:8]

    # Monthly duplicate attempts (approximated from fraud_labels)
    monthly_dup = []
    if not invoices_df.empty and not fraud_df.empty:
        merged_inv = invoices_df.reset_index(drop=True).merge(
            fraud_df.reset_index(drop=True)[["invoice_id", "ground_truth_label"]],
            on="invoice_id", how="left"
        )
        merged_inv["month"] = merged_inv["invoice_date"].astype(str).str[:7]
        dup = merged_inv[merged_inv["ground_truth_label"] == "DOUBLE_FINANCING"]
        monthly = dup.groupby("month").size().reset_index(name="count")
        for _, row in monthly.iterrows():
            monthly_dup.append({"month": str(row["month"]), "count": int(row["count"])})
        monthly_dup.sort(key=lambda x: x["month"])

    # Top risk sellers
    top_risk_sellers = []
    if not invoices_df.empty and not companies_df.empty and not risk_df.empty:
        merged = invoices_df.reset_index(drop=True).merge(
            companies_df[["company_id", "company_name"]].rename(columns={"company_id": "seller_id"}),
            on="seller_id", how="left"
        )
        merged = merged.merge(risk_df[["invoice_id", "risk_score"]].reset_index(drop=True),
                              on="invoice_id", how="left")
        seller_risk = merged.groupby("company_name")["risk_score"].mean().reset_index()
        seller_risk.sort_values("risk_score", ascending=False, inplace=True)
        for _, row in seller_risk.head(5).iterrows():
            top_risk_sellers.append({
                "name": str(row["company_name"]),
                "avg_risk": round(float(row["risk_score"]), 1)
            })

    # Amount by risk level
    amount_by_risk = []
    if not invoices_df.empty and not risk_df.empty:
        merged = invoices_df.reset_index(drop=True).merge(
            risk_df[["invoice_id", "risk_level"]].reset_index(drop=True),
            on="invoice_id", how="left"
        )
        grouped = merged.groupby("risk_level")["net_amount"].sum().reset_index()
        for _, row in grouped.iterrows():
            amount_by_risk.append({
                "level": str(row["risk_level"]),
                "amount_cr": round(float(row["net_amount"]) / 1e7, 2)
            })

    # Top-risk buyers are grouped from the buyer-side company join and risk scores.
    top_risk_buyers = []
    if not invoices_df.empty and not companies_df.empty and not risk_df.empty:
        merged = invoices_df.reset_index(drop=True).merge(
            companies_df[["company_id", "company_name"]].rename(columns={"company_id": "buyer_id"}),
            on="buyer_id", how="left"
        )
        merged = merged.merge(risk_df[["invoice_id", "risk_score"]].reset_index(drop=True), on="invoice_id", how="left")
        buyer_risk = merged.groupby("company_name")["risk_score"].mean().reset_index()
        buyer_risk.sort_values("risk_score", ascending=False, inplace=True)
        for _, row in buyer_risk.head(5).iterrows():
            if str(row["company_name"]) not in ("nan", ""):
                top_risk_buyers.append({"name": str(row["company_name"]), "avg_risk": round(float(row["risk_score"]), 1)})

    return AnalyticsSchema(
        risk_distribution=risk_dist,
        financing_by_lender=fin_by_lender,
        industry_risk=industry_risk,
        monthly_duplicates=monthly_dup,
        top_risk_sellers=top_risk_sellers,
        top_risk_buyers=top_risk_buyers,
        amount_by_risk=amount_by_risk,
    )
