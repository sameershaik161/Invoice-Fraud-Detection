"""
Risk Engine — deterministic multi-signal risk scoring.
Returns a structured result with score, level, signals, and recommended action.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional
from fastapi import HTTPException
from config import settings
import data_store
from schemas.schemas import (
    RiskLevel, RecommendedAction, RiskSignalSchema, EvidenceItemSchema,
    AuditEntrySchema, VerificationResultSchema
)


def _risk_level(score: int) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    elif score >= 60:
        return RiskLevel.HIGH
    elif score >= 30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _recommended_action(level: RiskLevel) -> RecommendedAction:
    mapping = {
        RiskLevel.LOW: RecommendedAction.PROCEED,
        RiskLevel.MEDIUM: RecommendedAction.MANUAL_REVIEW,
        RiskLevel.HIGH: RecommendedAction.HOLD_PAYOUT,
        RiskLevel.CRITICAL: RecommendedAction.HOLD_PAYOUT,
    }
    return mapping[level]


def _audit_ts() -> str:
    return datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]


def run_verification(invoice_id: str) -> VerificationResultSchema:
    start = time.perf_counter()
    audit: list[AuditEntrySchema] = []
    signals: list[RiskSignalSchema] = []
    evidence: list[EvidenceItemSchema] = []
    score = 0

    def log(event: str, detail: str, level: str = "info"):
        audit.append(AuditEntrySchema(
            timestamp=_audit_ts(),
            event=event,
            detail=detail,
            level=level,
        ))

    log("Invoice received", f"Processing verification for {invoice_id}")

    invoices_df = data_store.get("invoices")
    financing_df = data_store.get("financing")
    companies_df = data_store.get("companies")
    eway_df = data_store.get("eway_bills")
    fraud_df = data_store.get("fraud_labels")

    # -- CANONICAL INVOICE RESOLUTION (MODIFIED INVOICE IDENTIFIER CHECK) --
    from services.invoice_matcher import get_canonical_invoice_id
    canonical_id, is_modified_id = get_canonical_invoice_id(invoice_id)
    target_id = canonical_id if (canonical_id and canonical_id in invoices_df.index) else invoice_id

    # -- INVOICE EXISTS CHECK --
    if invoices_df.empty or target_id not in invoices_df.index:
        log("Invoice not found", f"{invoice_id} does not exist in dataset", "error")
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found.")

    if is_modified_id:
        log("Modified invoice identifier detected",
            f"Input ID '{invoice_id}' resolved to canonical record '{target_id}'", "warning")

    inv = invoices_df.loc[target_id]
    if hasattr(inv, "iloc") and len(inv.shape) > 1:
        inv = inv.iloc[0]

    seller_id = str(inv.get("seller_id", ""))
    buyer_id = str(inv.get("buyer_id", ""))
    net_amount = float(inv.get("net_amount", 0))

    log("Invoice identity confirmed", f"Seller: {seller_id}, Buyer: {buyer_id}, Amount: ₹{net_amount:,.0f}")

    # -- SELLER / BUYER DETAILS --
    seller_gstin, buyer_gstin = "", ""
    seller_name, buyer_name = seller_id, buyer_id

    if not companies_df.empty:
        if seller_id in companies_df.index:
            s_row = companies_df.loc[seller_id]
            if hasattr(s_row, "iloc") and len(s_row.shape) > 1:
                s_row = s_row.iloc[0]
            seller_gstin = str(s_row.get("gstin", ""))
            seller_name = str(s_row.get("company_name", seller_id))
        if buyer_id in companies_df.index:
            b_row = companies_df.loc[buyer_id]
            if hasattr(b_row, "iloc") and len(b_row.shape) > 1:
                b_row = b_row.iloc[0]
            buyer_gstin = str(b_row.get("gstin", ""))
            buyer_name = str(b_row.get("company_name", buyer_id))

    log("GSTIN project-data lookup", f"Seller GSTIN: {seller_gstin or 'N/A'}, Buyer GSTIN: {buyer_gstin or 'N/A'}; no external registry was queried")

    # -- SIGNAL 1: MULTIPLE LENDERS --
    inv_financing = financing_df[financing_df["invoice_id"] == target_id] if not financing_df.empty else None
    lender_count = 0
    financing_rows = []
    if inv_financing is not None and not inv_financing.empty:
        lender_count = len({str(value).strip() for value in inv_financing["lender_id"] if str(value).strip()})
        financing_rows = inv_financing.to_dict("records")

    multiple_lenders = lender_count > 1
    if multiple_lenders:
        score += settings.WEIGHT_MULTIPLE_LENDERS
        lender_names = [str(r.get("lender_id", "")) for r in financing_rows]
        log("Multiple lenders detected", f"Invoice financed by {lender_count} lenders: {', '.join(lender_names)}", "warning")

    signals.append(RiskSignalSchema(
        signal_id="MULTIPLE_LENDERS",
        name="Multiple Lender Financing",
        description="Invoice has been submitted to more than one lender for financing.",
        weight=settings.WEIGHT_MULTIPLE_LENDERS,
        triggered=multiple_lenders,
        value=str(lender_count),
    ))

    # -- SIGNAL 2: INVOICE SIMILARITY --
    similarity_score = 0.0
    similar_invoice_id = None
    try:
        from services.invoice_matcher import find_similar_invoices
        similars = find_similar_invoices(target_id, top_k=3, threshold=0.4)
        if similars:
            best = similars[0]
            sim_val = best["similarity"]
            similarity_score = sim_val
            similar_invoice_id = best["invoice_id"]
            if sim_val >= 0.7:
                boost = int(settings.WEIGHT_INVOICE_SIMILARITY * sim_val)
                score += boost
                log("High invoice similarity detected",
                    f"{similar_invoice_id} is {sim_val*100:.1f}% similar", "warning")
    except Exception as e:
        log("Similarity check skipped", str(e), "warning")

    signals.append(RiskSignalSchema(
        signal_id="INVOICE_SIMILARITY",
        name="Invoice Content Similarity",
        description="Measures how similar this invoice is to other invoices from the same seller/buyer.",
        weight=settings.WEIGHT_INVOICE_SIMILARITY,
        triggered=similarity_score >= 0.7,
        value=f"{similarity_score*100:.1f}%",
    ))

    # -- SIGNAL 3: GSTIN MATCH (seller seen with multiple lenders) --
    gstin_risk = False
    if seller_gstin and not financing_df.empty and not invoices_df.empty:
        # Reset index to ensure proper filtering
        invoices_reset = invoices_df.reset_index() if "invoice_id" not in invoices_df.columns else invoices_df
        seller_invoices_mask = invoices_reset["seller_id"] == seller_id
        seller_invoices = invoices_reset[seller_invoices_mask]["invoice_id"].tolist()
        if seller_invoices:
            seller_fin = financing_df[financing_df["invoice_id"].isin(seller_invoices)]
            unique_lenders = seller_fin["lender_id"].unique() if not seller_fin.empty else []
            if len(unique_lenders) > 2:
                gstin_risk = True
                score += settings.WEIGHT_GSTIN_MATCH
                log("GSTIN risk detected", f"Seller GSTIN {seller_gstin} appears with {len(unique_lenders)} lenders", "warning")

    signals.append(RiskSignalSchema(
        signal_id="GSTIN_MATCH",
        name="Seller GSTIN Multi-Lender Pattern",
        description="Seller GSTIN has been used across multiple lenders, creating a duplicate-risk pattern.",
        weight=settings.WEIGHT_GSTIN_MATCH,
        triggered=gstin_risk,
        value=seller_gstin or "N/A",
    ))

    # -- SIGNAL 4: DELIVERY PROOF HASH MATCH --
    delivery_match = False
    delivery_hash = None
    eway_row = None
    if not eway_df.empty:
        inv_eway = eway_df[eway_df["invoice_id"] == target_id]
        if not inv_eway.empty:
            eway_row = inv_eway.iloc[0]
            delivery_hash = str(eway_row.get("delivery_proof_hash", "")).strip()
            if delivery_hash:
                matching = eway_df[
                    (eway_df["delivery_proof_hash"].astype(str).str.strip() == delivery_hash) &
                    (eway_df["invoice_id"] != target_id)
                ]
                if not matching.empty:
                    delivery_match = True
                    score += settings.WEIGHT_DELIVERY_PROOF
                    log("Delivery proof hash collision", f"Hash {delivery_hash} matches {matching.iloc[0]['invoice_id']}", "warning")

    if delivery_hash:
        log("Delivery proof checked", f"E-Way Bill hash: {delivery_hash}")

    signals.append(RiskSignalSchema(
        signal_id="DELIVERY_PROOF",
        name="Delivery Proof Hash Match",
        description="Delivery proof hash matches another invoice — possible re-use of logistics documentation.",
        weight=settings.WEIGHT_DELIVERY_PROOF,
        triggered=delivery_match,
        value=delivery_hash or "N/A",
    ))

    # -- SIGNAL 5: TIMING OVERLAP --
    timing_risk = False
    timing_days = None
    if len(financing_rows) >= 2:
        try:
            dates = []
            for r in financing_rows:
                d = r.get("application_date", "")
                if d:
                    dates.append(datetime.strptime(str(d)[:10], "%Y-%m-%d"))
            if len(dates) >= 2:
                dates.sort()
                delta = (dates[-1] - dates[0]).days
                timing_days = delta
                if delta <= 14:
                    timing_risk = True
                    score += settings.WEIGHT_TIMING_OVERLAP
                    log("Suspicious timing overlap",
                        f"Two financing requests within {delta} days", "warning")
        except Exception:
            pass

    signals.append(RiskSignalSchema(
        signal_id="TIMING_OVERLAP",
        name="Financing Timing Overlap",
        description="Multiple financing applications submitted within a suspicious time window (≤14 days).",
        weight=settings.WEIGHT_TIMING_OVERLAP,
        triggered=timing_risk,
        value=f"{timing_days} days" if timing_days is not None else "N/A",
    ))

    # -- SIGNAL 6: HIGH VALUE --
    high_value = net_amount >= 5_00_000  # ≥ 5 lakh
    if high_value and multiple_lenders:
        score += settings.WEIGHT_HIGH_VALUE
        log("High-value invoice", f"₹{net_amount:,.0f} — above threshold", "info")

    signals.append(RiskSignalSchema(
        signal_id="HIGH_VALUE",
        name="High-Value Invoice",
        description="Invoice amount is above ₹5,00,000, amplifying the financial impact of any fraud.",
        weight=settings.WEIGHT_HIGH_VALUE,
        triggered=high_value,
        value=f"₹{net_amount:,.0f}",
    ))

    # -- SIGNAL 7: LINE-ITEM OVERLAP & RECYCLING --
    line_item_matched = False
    line_item_sim = 0.0
    matched_items_list = []
    matched_cand_inv = None
    try:
        from services.invoice_matcher import find_matching_line_items_in_dataset
        li_res = find_matching_line_items_in_dataset(target_id)
        line_item_matched = li_res.get("line_item_match", False)
        line_item_sim = float(li_res.get("similarity", 0.0))
        matched_items_list = li_res.get("matched_items", [])
        matched_cand_inv = li_res.get("matched_invoice_id")
        if line_item_matched:
            score += settings.WEIGHT_LINE_ITEM_SIMILARITY
            log("Line item recycling detected",
                f"Line items match {matched_cand_inv} with {line_item_sim*100:.0f}% similarity", "warning")
    except Exception as e:
        log("Line item check skipped", str(e), "warning")

    signals.append(RiskSignalSchema(
        signal_id="LINE_ITEM_SIMILARITY",
        name="Line-Item Overlap & Recycling",
        description="Line-item descriptions, HSN codes, and quantities match or duplicate another invoice.",
        weight=settings.WEIGHT_LINE_ITEM_SIMILARITY,
        triggered=line_item_matched,
        value=f"{line_item_sim*100:.0f}% similarity ({len(matched_items_list)} matched)" if line_item_matched else "No overlap",
    ))

    # -- SIGNAL 8: CIRCULAR BUYER-SUPPLIER NETWORK --
    circular_detected = False
    cycle_path = []
    cycle_len = 0
    cycle_desc = ""
    try:
        from services.graph_service import detect_circular_network
        cycle_res = detect_circular_network(seller_id, buyer_id)
        circular_detected = cycle_res.get("circular_network_detected", False)
        cycle_path = cycle_res.get("cycle", [])
        cycle_len = cycle_res.get("cycle_length", 0)
        cycle_desc = cycle_res.get("description", "")
        if circular_detected and cycle_len >= 2:
            score += settings.WEIGHT_CIRCULAR_NETWORK
            log("Circular trading network detected",
                f"Cycle detected across {cycle_len} entities: {' -> '.join(cycle_path)}", "warning")
    except Exception as e:
        log("Circular network check skipped", str(e), "warning")

    signals.append(RiskSignalSchema(
        signal_id="CIRCULAR_NETWORK",
        name="Circular Trading Network",
        description="Buyer-supplier circular network detected in transactional graph, indicating potential carousel fraud.",
        weight=settings.WEIGHT_CIRCULAR_NETWORK,
        triggered=circular_detected and cycle_len >= 2,
        value=f"Cycle length {cycle_len}: {' -> '.join(cycle_path[:4])}" if circular_detected else "No cycle",
    ))

    # -- SIGNAL 9: MODIFIED INVOICE NUMBER RESOLUTION --
    if is_modified_id:
        score += settings.WEIGHT_MODIFIED_INVOICE_ID

    signals.append(RiskSignalSchema(
        signal_id="MODIFIED_INVOICE_ID",
        name="Modified Invoice Number",
        description="Invoice number differs by punctuation or spacing from an existing canonical record.",
        weight=settings.WEIGHT_MODIFIED_INVOICE_ID,
        triggered=is_modified_id,
        value=f"Input: {invoice_id} -> Canonical: {target_id}" if is_modified_id else "Normal",
    ))

    # -- CLAMP SCORE --
    score = min(score, 100)
    level = _risk_level(score)
    action = _recommended_action(level)
    log("Risk score computed", f"Score: {score}/100 — {level.value}", "success" if score < 30 else "warning")
    log(f"Recommended action: {action.value}", "Verification complete", "success")

    # -- BUILD STRUCTURED EVIDENCE (8 CATEGORIES) --
    ev_step = 1

    # 1. Financing Evidence
    if multiple_lenders:
        lender_list = []
        for r in financing_rows:
            lender_list.append(f"{r.get('lender_id')} (₹{float(r.get('financed_amount',0)):,.0f})")
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="DOUBLE-FINANCING DETECTED",
            detail=f"Invoice {target_id} has been submitted to {lender_count} lenders: {', '.join(lender_list)}. This is the primary risk signal.",
            severity="critical"
        ))
        ev_step += 1

    # 2. Invoice Similarity Evidence
    if similarity_score >= 0.7 and similar_invoice_id:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="HIGH INVOICE SIMILARITY",
            detail=f"Invoice content is {similarity_score*100:.1f}% similar to {similar_invoice_id}. This suggests potential modification or duplicate submission.",
            severity="critical" if similarity_score >= 0.9 else "warning"
        ))
        ev_step += 1

    # 3. Line-Item Evidence
    if line_item_matched and matched_items_list:
        sample_item = matched_items_list[0]
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="LINE-ITEM RECYCLING DETECTED",
            detail=f"Line items match {matched_cand_inv} ({line_item_sim*100:.0f}% similarity): '{sample_item.get('item_a')}' (HSN {sample_item.get('hsn_a')}, Qty {sample_item.get('qty_a')}) vs '{sample_item.get('item_b')}' (HSN {sample_item.get('hsn_b')}, Qty {sample_item.get('qty_b')}).",
            severity="critical" if line_item_sim >= 0.85 else "warning"
        ))
        ev_step += 1

    # 4. Modified Invoice Identifier Evidence
    if is_modified_id:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="MODIFIED INVOICE IDENTIFIER",
            detail=f"Possible modified invoice identifier detected: input '{invoice_id}' resolved to canonical record '{target_id}'. Corroborating seller GSTIN, buyer GSTIN, and net amount verified against existing facility.",
            severity="warning"
        ))
        ev_step += 1

    # 5. Circular Buyer-Supplier Network Evidence
    if circular_detected and cycle_len >= 2:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="SUSPICIOUS NETWORK PATTERN",
            detail=cycle_desc or f"Circular buyer-supplier relationship detected across {cycle_len} entities: {' -> '.join(cycle_path)}. Entities engage in reciprocal factoring loop.",
            severity="warning"
        ))
        ev_step += 1

    # 6. GSTIN Evidence
    if seller_gstin:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="SELLER ENTITY MATCH",
                 detail=f"Seller {seller_name} with GSTIN {seller_gstin} is present in the project company data. " +
                     ("This GSTIN has been associated with suspicious multi-lender activity in project financing records." if gstin_risk else "No external GST registry was queried."),
            severity="warning" if gstin_risk else "safe"
        ))
        ev_step += 1

    if buyer_gstin:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="BUYER ENTITY MATCH",
            detail=f"Buyer {buyer_name} with GSTIN {buyer_gstin} identified as the receivable obligor.",
            severity="info"
        ))
        ev_step += 1

    # 7. Delivery Proof Hash Evidence
    if delivery_match and delivery_hash:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="DELIVERY PROOF COLLISION",
            detail=f"E-Way Bill hash {delivery_hash} matches another invoice's delivery record. Possible re-use of logistics documentation.",
            severity="warning"
        ))
        ev_step += 1

    # 8. Timeline Evidence
    if timing_risk and timing_days is not None:
        evidence.append(EvidenceItemSchema(
            step=ev_step, title="SUSPICIOUS TIMING",
            detail=f"Two financing applications were submitted only {timing_days} days apart — within the high-risk window of 14 days.",
            severity="warning"
        ))
        ev_step += 1

    if not evidence:
        evidence.append(EvidenceItemSchema(
            step=1, title="NO RISK SIGNALS TRIGGERED",
            detail=f"Invoice {target_id} passed all verification checks. Seller and buyer relationships appear normal.",
            severity="safe"
        ))

    # -- SUMMARY --
    triggered_count = sum(1 for s in signals if s.triggered)
    summary = (
        f"Invoice {target_id} scored {score}/100 ({level.value}). "
        f"{triggered_count}/{len(signals)} risk signals triggered. "
        f"Recommended action: {action.value.replace('_', ' ')}."
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    confidence = min(0.6 + triggered_count * 0.08, 0.98)

    return VerificationResultSchema(
        invoice_id=invoice_id,
        risk_score=score,
        risk_level=level,
        recommended_action=action,
        confidence=round(confidence, 2),
        lender_count=lender_count,
        duplicate_detected=multiple_lenders,
        verification_time_ms=elapsed_ms,
        signals=signals,
        evidence=evidence,
        audit_trail=audit,
        summary=summary,
    )

