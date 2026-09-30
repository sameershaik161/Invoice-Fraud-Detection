"""Evidence-grounded investigation copilot with a finite, read-only tool set."""
from __future__ import annotations

import asyncio
import re
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

import data_store
from config import settings
from routes.invoices import _build_detail
from services.graph_service import build_invoice_graph
from services.graph_service import detect_circular_network
from services.invoice_matcher import (
    find_matching_line_items_in_dataset,
    get_canonical_invoice_id,
)
from services.llm_provider import ALLOWED_INTENTS, build_llm_provider
from services.risk_engine import run_verification


INVOICE_PATTERN = re.compile(r"\bINV(?:[-/ ]?\d{4})?[-/ ]?\d{3,8}\b", re.IGNORECASE)
COMPANY_PATTERN = re.compile(r"\bCMP\d{3,8}\b", re.IGNORECASE)
LENDER_PATTERN = re.compile(r"\bLND\d{3,6}\b", re.IGNORECASE)
GSTIN_PATTERN = re.compile(r"\b\d{2}[A-Z0-9]{13}\b", re.IGNORECASE)
EWAY_PATTERN = re.compile(r"\bEWB\d{6,16}\b", re.IGNORECASE)


def _extract(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text or "")
    return match.group(0).upper() if match else None


def _looks_like_query_injection(text: str) -> bool:
    patterns = (
        r"\bMATCH\s*\(",
        r"\bRETURN\s+(?:\w|\$|\d)",
        r"\b(?:CREATE|MERGE)\s*\(",
        r"\bDETACH\s+DELETE\b",
        r"\bDELETE\s+\w+",
        r"\bDROP\s+(?:DATABASE|INDEX|CONSTRAINT|USER)\b",
        r"\bSET\s+\w+\.\w+",
        r"\bREMOVE\s+\w+\.\w+",
        r"\bCALL\s+(?:DB|APOC|GDS)\.",
    )
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in patterns)


def plan_intents(question: str, invoice_id: str | None = None) -> list[str]:
    """Map natural language to an allowlisted set; never produces query text."""
    text = (question or "").lower()
    intents: list[str] = []
    if any(term in text for term in ("what does this system", "how does", "how do", "what is invoice factoring guard")):
        intents.append("general_system_question")

    if invoice_id:
        intents.append("invoice_lookup")
    if any(term in text for term in ("risk", "risky", "score", "classified", "why", "investigat", "suspicious")):
        intents.extend(("risk_analysis", "evidence"))
    if any(term in text for term in ("financ", "lender", "funded", "who financed")):
        intents.append("financing_lookup")
    if any(term in text for term in ("duplicate", "multiple lender", "double financ")):
        intents.append("duplicate_financing")
    if any(term in text for term in ("network", "relationship", "connected", "circular", "cycle", "path", "graph")):
        intents.extend(("network_analysis", "circular_network"))
    if any(term in text for term in ("delivery", "delivered", "e-way", "eway", "proof")):
        intents.append("delivery_proof")
    if any(term in text for term in ("reuse", "reused", "collision")):
        intents.extend(("risk_analysis", "evidence"))
    if "gstin" in text or "gst" in text:
        intents.append("gstin_analysis")
    if any(term in text for term in ("line item", "line-item", "matching item", "similar item")):
        intents.append("line_item_matching")
    if any(term in text for term in ("similar invoice", "similar invoices", "compare invoices", "compare these invoices")):
        intents.append("similarity_lookup")
    if "timeline" in text or "chronolog" in text:
        intents.append("timeline")
    if any(term in text for term in ("report", "summary", "summarize", "summarise")):
        intents.extend(("report_generation", "risk_analysis", "financing_lookup", "network_analysis", "delivery_proof", "gstin_analysis", "timeline"))
    if COMPANY_PATTERN.search(question or "") or LENDER_PATTERN.search(question or "") or GSTIN_PATTERN.search(question or ""):
        intents.append("company_lookup" if COMPANY_PATTERN.search(question or "") or GSTIN_PATTERN.search(question or "") else "financing_lookup")
        intents.append("search_entities")
    if EWAY_PATTERN.search(question or "") or re.search(r"\b(search|look up|find)\b", text):
        intents.append("search_entities")
    if invoice_id and _extract(INVOICE_PATTERN, question or ""):
        raw_id = _extract(INVOICE_PATTERN, question or "") or ""
        canonical_id, modified = get_canonical_invoice_id(raw_id)
        if canonical_id and modified:
            intents.append("modified_invoice_id")
    if not intents:
        intents.append("invoice_lookup" if invoice_id else "unsupported_question")
    return list(dict.fromkeys(intents))


def _source(source_type: str, source_id: str, tool: str, confidence: float = 1.0) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "tool": tool,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
    }


def _run_entity_search(query: str) -> list[dict[str, Any]]:
    query = (query or "").strip()[:80]
    if len(query) < 2:
        return []
    try:
        from routes.investigation import search_entities
        response = asyncio.run(search_entities(query, limit=8))
        return response.get("results", [])[:8]
    except Exception:
        return []


def _action(label: str, href: str) -> dict[str, str]:
    return {"label": label, "href": href}


def _company_lookup(company_id: str | None, lender_id: str | None, gstin: str | None) -> tuple[list[dict], list[dict], list[dict]]:
    companies = data_store.get("companies")
    lenders = data_store.get("lenders")
    invoices = data_store.get("invoices")
    financing = data_store.get("financing")
    entities: list[dict] = []
    findings: list[dict] = []
    sources: list[dict] = []

    if company_id or gstin:
        if not companies.empty:
            mask = companies["company_id"].astype(str).str.upper().eq((company_id or "").upper()) if company_id else companies["gstin"].astype(str).str.upper().eq((gstin or "").upper())
            rows = companies[mask].head(5)
            for _, row in rows.iterrows():
                cid = str(row.get("company_id", ""))
                name = str(row.get("company_name", cid))
                company_gstin = str(row.get("gstin", ""))
                entities.append({"type": "company", "id": cid, "label": name, "href": f"/copilot?entityId={cid}&entityType=company"})
                related_ids: list[str] = []
                if not invoices.empty:
                    related = invoices[(invoices["seller_id"] == cid) | (invoices["buyer_id"] == cid)]
                    related_ids = related["invoice_id"].astype(str).tolist()
                lender_ids: list[str] = []
                if related_ids and not financing.empty:
                    lender_ids = sorted(financing[financing["invoice_id"].isin(related_ids)]["lender_id"].astype(str).unique().tolist())
                findings.append({"kind": "company", "title": name, "detail": f"Company {cid}; GSTIN {company_gstin or 'not available'}; linked to {len(lender_ids)} distinct lenders in financing records.", "value": {"company_id": cid, "gstin": company_gstin, "lender_count": len(lender_ids), "lender_ids": lender_ids[:20]}})
                sources.append(_source("CSV/Application Data", cid, "get_company_network"))

    if lender_id and not lenders.empty:
        rows = lenders[lenders["lender_id"].astype(str).str.upper().eq(lender_id.upper())].head(5)
        for _, row in rows.iterrows():
            lid = str(row.get("lender_id", ""))
            name = str(row.get("lender_name", lid))
            entities.append({"type": "lender", "id": lid, "label": name, "href": f"/copilot?entityId={lid}&entityType=lender"})
            findings.append({"kind": "lender", "title": name, "detail": f"Lender {lid} is present in the lender directory.", "value": {"lender_id": lid, "lender_type": str(row.get("lender_type", ""))}})
            sources.append(_source("CSV/Application Data", lid, "search_entities"))

    return findings, entities, sources


def _timeline(detail, risk) -> list[dict[str, str]]:
    events = [{"date": detail.invoice_date or "Date unavailable", "label": "Invoice Created", "detail": f"Invoice {detail.invoice_id} entered the ledger.", "severity": "info"}]
    for item in detail.financing_records:
        events.append({"date": item.application_date or "Date unavailable", "label": f"{item.lender_id} Financing", "detail": f"{item.lender_name} financed {detail.currency} {item.financed_amount:,.0f}.", "severity": "warning"})
    if detail.eway_bill and detail.eway_bill.movement_date:
        events.append({"date": detail.eway_bill.movement_date, "label": "Delivery Proof Recorded", "detail": f"E-way bill {detail.eway_bill.eway_bill_no}: {detail.eway_bill.delivery_status}.", "severity": "info"})
    events.append({"date": "Current verification", "label": "Risk Detected", "detail": risk.summary, "severity": "warning" if risk.risk_level.value in ("HIGH", "CRITICAL") else "info"})
    def event_date(event: dict[str, str]) -> datetime:
        try:
            return datetime.strptime(event["date"][:10], "%Y-%m-%d")
        except (KeyError, ValueError):
            return datetime.max

    events.sort(key=event_date)
    return events


def _company_network(company_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    invoices = data_store.get("invoices")
    if invoices.empty:
        return [], [], []
    related = invoices[(invoices["seller_id"] == company_id) | (invoices["buyer_id"] == company_id)].head(20)
    financing = data_store.get("financing")
    lenders = data_store.get("lenders")
    findings: list[dict[str, Any]] = []
    entities: list[dict[str, str]] = []
    cycles: list[list[str]] = []
    links: list[dict[str, str]] = []
    linked_invoice_ids: list[str] = []
    checked_pairs: set[tuple[str, str]] = set()
    for _, row in related.iterrows():
        seller_id = str(row.get("seller_id", ""))
        buyer_id = str(row.get("buyer_id", ""))
        invoice_id = str(row.get("invoice_id", ""))
        other_id = buyer_id if seller_id == company_id else seller_id
        if other_id:
            links.append({"invoice_id": invoice_id, "related_company_id": other_id, "direction": "sells_to" if seller_id == company_id else "buys_from"})
            linked_invoice_ids.append(invoice_id)
            entities.append({"type": "invoice", "id": invoice_id, "label": invoice_id, "href": f"/investigation/{invoice_id}"})
            if other_id != company_id:
                entities.append({"type": "company", "id": other_id, "label": other_id, "href": f"/copilot?entityId={other_id}&entityType=company"})
        pair = (seller_id, buyer_id)
        if seller_id and buyer_id and pair not in checked_pairs and len(checked_pairs) < 5:
            checked_pairs.add(pair)
            try:
                cycle = detect_circular_network(seller_id, buyer_id, max_depth=5)
                if cycle.get("circular_network_detected"):
                    cycles.append(cycle.get("cycle", []))
            except Exception:
                pass
    entities = list({(item["type"], item["id"]): item for item in entities}.values())[:25]
    if links:
        lender_ids: list[str] = []
        lender_names: dict[str, str] = {}
        if not financing.empty:
            lender_ids = sorted(financing[financing["invoice_id"].isin(linked_invoice_ids)]["lender_id"].astype(str).unique().tolist())
        if lender_ids and not lenders.empty:
            lender_names = dict(zip(lenders["lender_id"].astype(str), lenders["lender_name"].astype(str)))
        entities.extend({"type": "lender", "id": lender_id, "label": lender_names.get(lender_id, lender_id), "href": "/risk"} for lender_id in lender_ids[:20])
        findings.append({
            "kind": "network",
            "title": f"{len(links)} linked invoices",
            "detail": f"Found {len(links)} of at most 20 invoice relationships for {company_id}; checked up to five invoice pairs for a circular path.",
            "value": {"links": links, "cycles": cycles, "lender_ids": lender_ids[:20]},
        })
    sources = [_source("CSV/Application Data", company_id, "get_company_network")] if links else []
    return findings, entities, sources


def _deterministic_answer(question: str, invoice_id: str | None, detail, risk, graph, line_result, findings: list[dict]) -> str:
    if not invoice_id and findings:
        return "\n".join(f"{item['title']}: {item['detail']}" for item in findings)
    if not invoice_id and "general_system_question" in plan_intents(question):
        return ("Invoice Factoring Guard detects duplicate financing across lenders and combines risk signals, "
                "company relationships, delivery evidence, GSTIN patterns, and audit evidence. "
                "Its records are synthetic demo data; no live banking or GST portal is queried.")
    if not invoice_id:
        return "I couldn't find verified data for that query. Provide an invoice, company, lender, or GSTIN identifier, or ask what the system checks."

    lines = [f"Investigation for {invoice_id}:"]
    if detail:
        lines.append(f"Seller: {detail.seller_name} ({detail.seller_id}); buyer: {detail.buyer_name} ({detail.buyer_id}); amount: {detail.currency} {detail.net_amount:,.2f}.")
        if "gstin_analysis" in plan_intents(question, invoice_id):
            lines.append(f"GSTINs: seller {detail.seller_gstin or 'not available'}; buyer {detail.buyer_gstin or 'not available'}.")
        if "financing_lookup" in plan_intents(question, invoice_id) or "duplicate_financing" in plan_intents(question, invoice_id) or "report_generation" in plan_intents(question, invoice_id):
            lenders = ", ".join(f"{item.lender_id} ({item.status}, {detail.currency} {item.financed_amount:,.2f})" for item in detail.financing_records) or "no financing records found"
            lines.append(f"Financing records ({len(detail.financing_records)}): {lenders}.")
        if detail.eway_bill and ("delivery_proof" in plan_intents(question, invoice_id) or "report_generation" in plan_intents(question, invoice_id)):
            lines.append(f"Delivery: {detail.eway_bill.delivery_status}; e-way bill {detail.eway_bill.eway_bill_no}; proof hash {detail.eway_bill.delivery_proof_hash}.")
    if risk:
        triggered = [signal.name for signal in risk.signals if signal.triggered]
        lines.append(f"Computed risk: {risk.risk_score}/100 ({risk.risk_level.value}); recommended action: {risk.recommended_action.value}.")
        if triggered:
            lines.append("Triggered signals: " + "; ".join(triggered) + ".")
    if graph and "network_analysis" in plan_intents(question, invoice_id):
        lines.append(f"Neo4j graph returned {len(graph.nodes)} nodes and {len(graph.edges)} relationships.")
        cycle = next((item["detail"] for item in findings if item["kind"] == "network"), None)
        if cycle:
            lines.append(cycle)
    if line_result is not None:
        if line_result.get("line_item_match"):
            lines.append(f"Line-item overlap found with {line_result.get('matched_invoice_id')} at {line_result.get('similarity')} similarity.")
        else:
            lines.append(f"No line-item match was found. The matcher compared {line_result.get('total_items_a', 0)} items; no pair met its match criteria.")
    if detail and "timeline" in plan_intents(question, invoice_id):
        for event in _timeline(detail, risk):
            lines.append(f"{event['date']}: {event['label']} — {event['detail']}")
    return "\n".join(lines)


def _build_report(invoice_id: str, findings: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> str:
    lines = ["INVOICE FACTORING GUARD — INVESTIGATION REPORT", f"Invoice: {invoice_id}", ""]
    sections = {"invoice": "Invoice", "risk": "Risk", "financing": "Financing", "delivery": "Delivery", "gstin": "GSTIN", "network": "Network", "line_items": "Line Items", "modified_id": "Identifier Resolution"}
    for finding in findings:
        title = sections.get(finding.get("kind", ""), finding.get("kind", "Finding").replace("_", " ").title())
        lines.extend((f"{title}: {finding.get('title', 'Finding')}", str(finding.get("detail", ""))))
        if finding.get("kind") == "financing" and isinstance(finding.get("value"), list):
            for record in finding["value"]:
                lines.append(f"- {record.get('lender_id')}: {record.get('status')}, {record.get('financed_amount')} on {record.get('application_date')}")
        if finding.get("kind") == "timeline" and isinstance(finding.get("value"), list):
            lines.append("Timeline:")
            for event in finding["value"]:
                lines.append(f"- {event.get('date')}: {event.get('label')} — {event.get('detail')}")
        lines.append("")
    lines.append("Evidence and Sources:")
    for item in evidence:
        title = item.get("title") or item.get("source_type", "Source")
        detail = item.get("detail", "")
        source = f" [{item.get('source_type')}: {item.get('source_id')}]" if item.get("source_type") else ""
        lines.append(f"- {title}: {detail}{source}".strip())
    return "\n".join(lines)


def build_grounded_answer(
    message: str,
    history: list[dict],
    context_invoice_id: str | None,
    context_entity_id: str | None = None,
    context_entity_type: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    provider = build_llm_provider(settings)
    if _looks_like_query_injection(message):
        return {
            "answer": "I can only answer investigation questions through the approved read-only tools. Arbitrary Cypher and database operations are not accepted.",
            "intents": [], "tools": [], "findings": [], "entities": [], "evidence": [], "actions": [],
            "invoice_id": context_invoice_id, "llm_used": False, "fallback_reason": "unsafe_query_rejected",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    history_text = " ".join(str(item.get("content", ""))[:1000] for item in history[-8:])
    context_entity_id = context_entity_id or context_invoice_id
    context_entity_type = context_entity_type or ("invoice" if context_invoice_id else None)
    raw_invoice_id = context_invoice_id or (context_entity_id if context_entity_type == "invoice" else None) or _extract(INVOICE_PATTERN, message) or _extract(INVOICE_PATTERN, history_text)
    invoice_id: str | None = None
    modified_id = False
    if raw_invoice_id:
        invoice_id, modified_id = get_canonical_invoice_id(raw_invoice_id)
        if not invoice_id:
            return {
                "answer": "I couldn't find verified data for that invoice ID.",
                "intents": ["invoice_lookup"], "tools": ["resolve_invoice_id"], "findings": [], "entities": [],
                "evidence": [], "actions": [], "invoice_id": None, "llm_used": False,
                "fallback_reason": "invoice_not_found", "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    intents = plan_intents(message, raw_invoice_id)
    planned_intents, planner_provider = provider.plan(message, context_entity_id, history)
    if planned_intents:
        intents = list(dict.fromkeys([*intents, *(intent for intent in planned_intents if intent in ALLOWED_INTENTS)]))
    tools: list[str] = []
    findings: list[dict[str, Any]] = []
    entities: list[dict[str, str]] = []
    evidence: list[dict[str, Any]] = []
    detail = None
    risk = None
    graph = None
    line_result = None

    company_id = _extract(COMPANY_PATTERN, message) or (context_entity_id if context_entity_type == "company" else None)
    lender_id = _extract(LENDER_PATTERN, message) or (context_entity_id if context_entity_type == "lender" else None)
    gstin = _extract(GSTIN_PATTERN, message) or (context_entity_id if context_entity_type == "gstin" else None)
    eway_id = _extract(EWAY_PATTERN, message)
    search_query = eway_id or company_id or lender_id or gstin or _extract(INVOICE_PATTERN, message)
    if not search_query and "search_entities" in intents and "line_item_matching" not in intents:
        term = re.search(r"\b(?:search|look up|find)\s+(?:for\s+)?([a-z0-9][a-z0-9 ._-]{1,70})", message, re.IGNORECASE)
        search_query = term.group(1).strip() if term else None
    if "search_entities" in intents and search_query:
        search_results = _run_entity_search(search_query)
        if search_results:
            tools.append("search_entities")
            for item in search_results:
                entity = {"type": item.get("type", "entity").lower(), "id": item.get("id", ""), "label": item.get("label", ""), "href": item.get("route", "/invoices")}
                if entity["type"] == "companies":
                    entity["href"] = f"/copilot?entityId={entity['id']}&entityType=company"
                elif entity["type"] == "lenders":
                    entity["href"] = f"/copilot?entityId={entity['id']}&entityType=lender"
                entities.append(entity)
            findings.append({"kind": "search", "title": f"{len(search_results)} search results", "detail": "; ".join(item.get("label", item.get("id", "")) for item in search_results), "value": search_results})
            evidence.append(_source("Global Search", search_query, "search_entities"))
    if company_id:
        intents = list(dict.fromkeys([*intents, "company_lookup", "search_entities"]))
    other_findings, other_entities, other_sources = _company_lookup(company_id, lender_id, gstin)
    findings.extend(other_findings)
    entities.extend(other_entities)
    evidence.extend(other_sources)
    if other_findings:
        tools.append("search_entities")
    if company_id and any(intent in intents for intent in ("network_analysis", "circular_network")):
        network_findings, network_entities, network_sources = _company_network(company_id)
        findings.extend(network_findings)
        entities.extend(network_entities)
        evidence.extend(network_sources)
        tools.append("get_company_network")

    if invoice_id:
        try:
            detail = _build_detail(invoice_id)
            tools.append("get_invoice")
            entities.extend([
                {"type": "invoice", "id": invoice_id, "label": invoice_id, "href": f"/invoices/{invoice_id}"},
                {"type": "company", "id": detail.seller_id, "label": detail.seller_name, "href": f"/copilot?entityId={detail.seller_id}&entityType=company"},
                {"type": "company", "id": detail.buyer_id, "label": detail.buyer_name, "href": f"/copilot?entityId={detail.buyer_id}&entityType=company"},
            ])
            evidence.append(_source("Invoice Database", invoice_id, "get_invoice"))
            findings.append({"kind": "invoice", "title": invoice_id, "detail": f"{detail.seller_name} billed {detail.buyer_name} {detail.currency} {detail.net_amount:,.2f} on {detail.invoice_date}.", "value": {"seller_id": detail.seller_id, "buyer_id": detail.buyer_id, "line_item_count": len(detail.line_items)}})
        except HTTPException:
            detail = None

        needs_risk = any(intent in intents for intent in ("risk_analysis", "evidence", "duplicate_financing", "circular_network", "gstin_analysis", "report_generation"))
        if detail and needs_risk:
            try:
                risk = run_verification(invoice_id)
                tools.append("get_invoice_risk")
                evidence.append(_source("Risk Engine", invoice_id, "get_invoice_risk"))
                findings.append({"kind": "risk", "title": f"{risk.risk_score}/100 {risk.risk_level.value}", "detail": risk.summary, "value": {"score": risk.risk_score, "level": risk.risk_level.value, "signals": [s.model_dump(mode="json") for s in risk.signals if s.triggered]}})
                evidence.extend({**item.model_dump(mode="json"), "source_type": "Risk Engine", "source_id": invoice_id, "tool": "get_invoice_risk", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 1.0} for item in risk.evidence)
            except Exception:
                risk = None

        if detail and "financing_lookup" in intents:
            tools.append("get_financing_records")
            for item in detail.financing_records:
                entities.append({"type": "lender", "id": item.lender_id, "label": item.lender_name, "href": f"/copilot?entityId={item.lender_id}&entityType=lender"})
            findings.append({"kind": "financing", "title": f"{len(detail.financing_records)} financing records", "detail": ", ".join(item.lender_id for item in detail.financing_records) or "No financing records found.", "value": [item.model_dump(mode="json") for item in detail.financing_records]})
            evidence.append(_source("CSV/Application Data", invoice_id, "get_financing_records"))

        if detail and "delivery_proof" in intents:
            tools.append("get_delivery_proof")
            if detail.eway_bill:
                collision = next((item.detail for item in (risk.evidence if risk else []) if item.title == "DELIVERY PROOF COLLISION"), None)
                delivery_detail = f"E-way bill {detail.eway_bill.eway_bill_no}; proof hash {detail.eway_bill.delivery_proof_hash}."
                if collision:
                    delivery_detail += f" {collision}"
                findings.append({"kind": "delivery", "title": detail.eway_bill.delivery_status, "detail": delivery_detail, "value": detail.eway_bill.model_dump(mode="json")})
                evidence.append(_source("Delivery Data", detail.eway_bill.eway_bill_no, "get_delivery_proof"))
            else:
                findings.append({"kind": "delivery", "title": "No delivery proof found", "detail": "The current dataset has no delivery proof linked to this invoice.", "value": None})

        if detail and "gstin_analysis" in intents:
            tools.append("get_gstin_evidence")
            gstin_pattern = next((entry.detail for entry in (risk.audit_trail if risk else []) if entry.event == "GSTIN risk detected"), None)
            gstin_detail = f"Seller {detail.seller_gstin or 'not available'}; buyer {detail.buyer_gstin or 'not available'}."
            if gstin_pattern:
                gstin_detail += f" {gstin_pattern}"
            findings.append({"kind": "gstin", "title": "Seller and buyer GSTIN", "detail": gstin_detail, "value": {"seller_gstin": detail.seller_gstin, "buyer_gstin": detail.buyer_gstin, "risk_pattern": gstin_pattern}})
            evidence.append(_source("CSV/Application Data", invoice_id, "get_gstin_evidence"))

        if detail and any(intent in intents for intent in ("network_analysis", "circular_network")):
            tools.extend(("get_related_entities", "detect_circular_network"))
            try:
                graph = build_invoice_graph(invoice_id)
                cycle_signal = next((s for s in (risk.signals if risk else []) if s.signal_id == "CIRCULAR_NETWORK"), None)
                findings.append({"kind": "network", "title": "Invoice relationship graph", "detail": f"Neo4j graph returned {len(graph.nodes)} nodes and {len(graph.edges)} edges." + (f" {cycle_signal.value}." if cycle_signal and cycle_signal.triggered else ""), "value": {"nodes": len(graph.nodes), "edges": len(graph.edges), "edge_types": sorted({edge.label for edge in graph.edges})}})
                evidence.append(_source("Neo4j", invoice_id, "get_related_entities"))
            except Exception:
                findings.append({"kind": "network", "title": "Graph unavailable", "detail": "Neo4j graph data could not be reached; CSV-backed invoice evidence remains available.", "value": None})

        if detail and "line_item_matching" in intents:
            tools.append("match_invoice_line_items")
            try:
                line_result = find_matching_line_items_in_dataset(invoice_id)
                findings.append({"kind": "line_items", "title": "Line-item comparison", "detail": f"{line_result.get('total_items_a', 0)} invoice line items; match={bool(line_result.get('line_item_match'))}; similarity={line_result.get('similarity', 0)}.", "value": line_result})
                evidence.append(_source("CSV/Application Data", invoice_id, "match_invoice_line_items"))
            except Exception:
                findings.append({"kind": "line_items", "title": "Line-item comparison unavailable", "detail": "Line-item comparison could not be completed.", "value": None})

        if detail and "similarity_lookup" in intents:
            tools.append("find_similar_invoices")
            from services.invoice_matcher import find_similar_invoices
            similar = find_similar_invoices(invoice_id, top_k=5, threshold=0.4)
            findings.append({"kind": "similar_invoices", "title": f"{len(similar)} similar invoices", "detail": "; ".join(item["invoice_id"] for item in similar) or "No similar invoices met the matcher threshold.", "value": similar})
            evidence.append(_source("CSV/Application Data and Invoice Matcher", invoice_id, "find_similar_invoices"))

        if detail and "timeline" in intents:
            tools.append("get_invoice_timeline")
            if risk is None:
                try:
                    risk = run_verification(invoice_id)
                except Exception:
                    risk = None
            findings.append({"kind": "timeline", "title": "Investigation timeline", "detail": f"{len(detail.financing_records)} financing events and {'a delivery event' if detail.eway_bill else 'no delivery event'} are available.", "value": _timeline(detail, risk) if risk else []})
            evidence.append(_source("CSV/Application Data and Risk Engine", invoice_id, "get_invoice_timeline"))

        if modified_id:
            tools.append("resolve_invoice_id")
            findings.append({"kind": "modified_id", "title": "Modified invoice ID resolved", "detail": f"{raw_invoice_id} resolves to canonical invoice {invoice_id}.", "value": {"input": raw_invoice_id, "canonical_invoice_id": invoice_id}})
            evidence.append(_source("Invoice Database", invoice_id, "resolve_invoice_id"))

    actions: list[dict[str, str]] = []
    if invoice_id:
        actions = [
            _action("Open Invoice", f"/invoices/{invoice_id}"),
            _action("Open Investigation", f"/investigation/{invoice_id}"),
            _action("View Risk", f"/verify?id={invoice_id}"),
            _action("Open Graph", f"/graph?id={invoice_id}"),
            _action("View Financing", f"/investigation/{invoice_id}"),
            _action("View Timeline", f"/investigation/{invoice_id}"),
            _action("View Evidence", f"/investigation/{invoice_id}"),
            _action("Generate Report", f"/investigation/{invoice_id}"),
        ]
    elif company_id and "network_analysis" in intents:
        company_network = next((item for item in findings if item["kind"] == "network"), None)
        links = company_network.get("value", {}).get("links", []) if company_network else []
        if links:
            actions = [
                _action("Open Graph", f"/graph?id={links[0]['invoice_id']}"),
                _action("View Company Invoices", f"/invoices?search={company_id}"),
            ]

    answer = _deterministic_answer(message, invoice_id, detail, risk, graph, line_result, findings)
    report_text = _build_report(invoice_id, findings, evidence) if invoice_id and "report_generation" in intents else None
    for index, item in enumerate(evidence, start=1):
        item["ref_id"] = f"E{index}"
        if item.get("source_type") == "Neo4j":
            item["href"] = f"/graph?id={invoice_id}" if invoice_id else "/graph"
        elif item.get("source_type") == "Risk Engine":
            item["href"] = f"/verify?id={invoice_id}" if invoice_id else "/risk"
        elif item.get("source_type") == "Delivery Data":
            item["href"] = f"/investigation/{invoice_id}" if invoice_id else "/invoices"
        else:
            item["href"] = f"/invoices/{invoice_id}" if invoice_id else "/invoices"
    evidence_for_finding = {
        "invoice": {"Invoice Database"},
        "risk": {"Risk Engine"},
        "financing": {"CSV/Application Data"},
        "delivery": {"Delivery Data"},
        "gstin": {"CSV/Application Data", "Risk Engine"},
        "network": {"Neo4j", "CSV/Application Data"},
        "line_items": {"CSV/Application Data"},
        "similar_invoices": {"CSV/Application Data and Invoice Matcher"},
        "timeline": {"CSV/Application Data and Risk Engine"},
    }
    for finding in findings:
        allowed_sources = evidence_for_finding.get(finding.get("kind"), set())
        finding["evidence_refs"] = [item["ref_id"] for item in evidence if item.get("source_type") in allowed_sources]

    citations = [{"id": item["ref_id"], "source_type": item.get("source_type"), "source_id": item.get("source_id"), "href": item.get("href")} for item in evidence]
    fallback_reason = "ai_provider_not_configured" if not provider.configured else "ai_provider_unavailable"
    llm_used = False
    llm_provider_used = None
    tool_ms = round((time.perf_counter() - started) * 1000, 2)
    llm_start = time.perf_counter()
    if provider.configured and evidence:
        system = (
            "You are an evidence-first invoice investigation explainer. Use only supplied findings and evidence. "
            "Return JSON with claims, an array of {text,evidence_refs}. Every factual claim must cite one or more "
            "provided evidence reference IDs. If evidence is insufficient, say so. Never assert guilt or fraud as fact, "
            "invent values, or provide new IDs. Do not return queries or instructions."
        )
        prompt = json.dumps({"question": message[:1200], "findings": findings[:20], "evidence": evidence[:30]}, ensure_ascii=True, default=str)
        generated = provider.generate(system, prompt, json_mode=True)
        if generated:
            try:
                parsed = json.loads(generated.text)
                claims = parsed.get("claims", []) if isinstance(parsed, dict) else []
                allowed_refs = {item["id"] for item in citations}
                valid_claims = [
                    claim for claim in claims[:8]
                    if isinstance(claim, dict)
                    and isinstance(claim.get("text"), str)
                    and claim["text"].strip()
                    and isinstance(claim.get("evidence_refs"), list)
                    and claim["evidence_refs"]
                    and all(reference in allowed_refs for reference in claim["evidence_refs"])
                ]
                if valid_claims and len(valid_claims) == len(claims[:8]):
                    answer = "\n".join(f"{claim['text'].strip()} [{', '.join(claim['evidence_refs'])}]" for claim in valid_claims)[:5000]
                    llm_used = True
                    llm_provider_used = generated.provider
                    fallback_reason = None
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

    return {
        "answer": answer,
        "intents": intents,
        "tools": list(dict.fromkeys(tools)),
        "findings": findings,
        "entities": entities,
        "evidence": evidence,
        "citations": citations,
        "actions": actions,
        "report_text": report_text,
        "invoice_id": invoice_id,
        "llm_used": llm_used,
        "provider": llm_provider_used or (provider.provider_names[0] if provider.configured else "none"),
        "planner_provider": planner_provider,
        "fallback_reason": fallback_reason,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "tool_latency_ms": tool_ms,
        "llm_latency_ms": round((time.perf_counter() - llm_start) * 1000, 2) if llm_used else 0.0,
    }
