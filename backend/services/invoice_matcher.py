"""
Invoice Matcher — TF-IDF + cosine similarity engine for duplicate detection.
Also handles normalized invoice number matching.
"""
from __future__ import annotations

import re
import numpy as np
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import data_store


def _normalize_invoice_number(inv_id: str) -> str:
    """Strip non-alphanumeric chars, lowercase — INV-1024 ≈ INV1024 ≈ inv/1024."""
    if not inv_id:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(inv_id).lower())


_NORMALIZED_MAP: dict[str, str] = {}


def get_normalized_map() -> dict[str, str]:
    global _NORMALIZED_MAP
    if not _NORMALIZED_MAP:
        invoices_df = data_store.get("invoices")
        if not invoices_df.empty:
            for inv_id in invoices_df.index:
                norm = _normalize_invoice_number(str(inv_id))
                if norm and norm not in _NORMALIZED_MAP:
                    _NORMALIZED_MAP[norm] = str(inv_id)
    return _NORMALIZED_MAP


def get_canonical_invoice_id(inv_id: str) -> tuple[Optional[str], bool]:
    """
    Returns (canonical_invoice_id, is_modified_id).
    - If inv_id directly exists in invoices table: returns (inv_id, False).
    - If inv_id matches an invoice after stripping punctuation/casing: returns (canonical_id, True).
    - If unknown: returns (None, False).
    """
    if not inv_id:
        return None, False
    invoices_df = data_store.get("invoices")
    if not invoices_df.empty and inv_id in invoices_df.index:
        return inv_id, False

    nmap = get_normalized_map()
    norm = _normalize_invoice_number(inv_id)
    if norm in nmap:
        return nmap[norm], True

    return None, False


def _build_invoice_text(row) -> str:
    """Create a comparable text blob from an invoice row."""
    parts = [
        str(row.get("invoice_id", "")),
        str(row.get("seller_id", "")),
        str(row.get("buyer_id", "")),
        str(row.get("primary_line_item", "")),
        str(row.get("net_amount", "")),
        str(row.get("invoice_date", "")),
    ]
    return " ".join(parts)


def compute_similarity(inv_id_a: str, inv_id_b: str) -> float:
    """Return cosine similarity between two invoices (0.0–1.0)."""
    invoices_df = data_store.get("invoices")
    if invoices_df.empty:
        return 0.0

    try:
        row_a = invoices_df.loc[inv_id_a]
        row_b = invoices_df.loc[inv_id_b]
    except KeyError:
        return 0.0

    text_a = _build_invoice_text(row_a)
    text_b = _build_invoice_text(row_b)

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    try:
        tfidf = vectorizer.fit_transform([text_a, text_b])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return float(sim)
    except Exception:
        return 0.0


def find_similar_invoices(inv_id: str, top_k: int = 5, threshold: float = 0.5) -> list[dict]:
    """Find top-k most similar invoices using seller/buyer/amount matching."""
    invoices_df = data_store.get("invoices")
    if invoices_df.empty or inv_id not in invoices_df.index:
        return []

    target = invoices_df.loc[inv_id]
    # Handle potential DataFrame (duplicate indices)
    if hasattr(target, "iloc") and len(target.shape) > 1:
        target = target.iloc[0]
    
    seller_id = target.get("seller_id", "")
    buyer_id = target.get("buyer_id", "")
    amount = float(target.get("net_amount", 0))

    # Fast pre-filter: same seller or same buyer
    # Reset index to ensure proper boolean filtering
    invoices_reset = invoices_df.reset_index() if "invoice_id" not in invoices_df.columns else invoices_df
    mask = (invoices_reset["seller_id"] == seller_id) | (invoices_reset["buyer_id"] == buyer_id)
    mask &= (invoices_reset["invoice_id"] != inv_id)
    candidates = invoices_reset[mask].head(200)

    if candidates.empty:
        return []

    results = []
    target_text = _build_invoice_text(target)

    for _, row in candidates.iterrows():
        candidate_text = _build_invoice_text(row)
        try:
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            tfidf = vectorizer.fit_transform([target_text, candidate_text])
            sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except Exception:
            sim = 0.0

        # Boost similarity when amount is within 5%
        candidate_amount = float(row.get("net_amount", 0))
        if amount > 0 and abs(candidate_amount - amount) / amount < 0.05:
            sim = min(sim + 0.15, 1.0)

        # Boost for normalized invoice number match
        if _normalize_invoice_number(str(inv_id)) == _normalize_invoice_number(str(row.get("invoice_id", ""))):
            sim = min(sim + 0.2, 1.0)

        if sim >= threshold:
            results.append({
                "invoice_id": row.get("invoice_id"),
                "similarity": round(sim, 4),
                "seller_id": row.get("seller_id"),
                "buyer_id": row.get("buyer_id"),
                "net_amount": candidate_amount,
                "invoice_date": str(row.get("invoice_date", "")),
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def check_normalized_match(inv_id_a: str, inv_id_b: str) -> bool:
    """Check if two invoice IDs are likely the same after normalization."""
    return _normalize_invoice_number(inv_id_a) == _normalize_invoice_number(inv_id_b)


# Standard Indian GST HSN codes and tax rates for B2B supply chain commodities
PRODUCT_HSN_MAP: dict[str, tuple[str, float]] = {
    "steel rods": ("7214", 18.0),
    "steel reinforcement rods": ("7214", 18.0),
    "steel coil": ("7208", 18.0),
    "aluminium sheet": ("7606", 18.0),
    "copper wire": ("7408", 18.0),
    "pvc pipes": ("3917", 18.0),
    "hydraulic pump": ("8413", 18.0),
    "industrial motor": ("8501", 18.0),
    "cnc parts": ("8466", 18.0),
    "pcb modules": ("8534", 18.0),
    "bearing assembly": ("8482", 18.0),
    "power supplies": ("8504", 18.0),
    "sensors": ("9031", 18.0),
    "led panels": ("8528", 18.0),
    "cement bags": ("2523", 28.0),
    "tiles": ("6907", 18.0),
    "api batch": ("3004", 12.0),
    "vaccine vials": ("3002", 5.0),
    "medical consumables": ("3005", 12.0),
    "tablet packaging": ("3923", 18.0),
    "cotton fabric": ("5208", 5.0),
    "denim roll": ("5209", 5.0),
    "garment batch": ("6203", 12.0),
    "polyester yarn": ("5402", 12.0),
    "processed grains": ("1006", 5.0),
    "rice bags": ("1006", 5.0),
    "edible oil": ("1512", 5.0),
    "spices": ("0910", 5.0),
    "polymer resin": ("3901", 18.0),
}


def get_line_item_details(item_desc: str) -> tuple[str, float]:
    """Return standard (HSN code, GST rate %) for a given item description."""
    norm = item_desc.strip().lower()
    for key, (hsn, gst) in PRODUCT_HSN_MAP.items():
        if key in norm or norm in key:
            return hsn, gst
    return ("9988", 18.0)


def compare_line_items_between_invoices(inv_id_a: str, inv_id_b: str) -> dict:
    """
    Compares the actual line items table between two invoices.
    Uses item description similarity, exact HSN code matching, quantity matching, and unit price/total matching.
    Returns structured matching details with similarity score and matched pairs.
    """
    line_items_df = data_store.get("line_items")
    if line_items_df.empty:
        return {"line_item_match": False, "similarity": 0.0, "matched_items": [], "total_items_a": 0, "total_items_b": 0}

    items_a = line_items_df[line_items_df["invoice_id"] == inv_id_a]
    items_b = line_items_df[line_items_df["invoice_id"] == inv_id_b]

    if items_a.empty or items_b.empty:
        return {"line_item_match": False, "similarity": 0.0, "matched_items": [], "total_items_a": len(items_a), "total_items_b": len(items_b)}

    matched_pairs = []
    total_score = 0.0
    used_b_indices = set()

    for _, row_a in items_a.iterrows():
        desc_a = str(row_a.get("item_description", "")).strip()
        qty_a = float(row_a.get("quantity", 0))
        amt_a = float(row_a.get("line_total", 0))
        price_a = float(row_a.get("unit_price", 0))
        hsn_a, gst_a = get_line_item_details(desc_a)

        best_sim = 0.0
        best_b = None
        best_b_idx = None

        for b_idx, row_b in items_b.iterrows():
            if b_idx in used_b_indices:
                continue
            desc_b = str(row_b.get("item_description", "")).strip()
            qty_b = float(row_b.get("quantity", 0))
            amt_b = float(row_b.get("line_total", 0))
            price_b = float(row_b.get("unit_price", 0))
            hsn_b, gst_b = get_line_item_details(desc_b)

            # 1. HSN code exact match (30%)
            hsn_match = 1.0 if hsn_a == hsn_b else 0.0

            # 2. Description text similarity via word overlap (30%)
            words_a = set(re.findall(r"\w+", desc_a.lower()))
            words_b = set(re.findall(r"\w+", desc_b.lower()))
            jaccard = len(words_a & words_b) / max(len(words_a | words_b), 1)

            # 3. Quantity similarity (20%)
            if qty_a > 0 and qty_b > 0:
                qty_diff = abs(qty_a - qty_b) / max(qty_a, qty_b)
                qty_sim = max(0.0, 1.0 - qty_diff)
            else:
                qty_sim = 1.0 if qty_a == qty_b else 0.0

            # 4. Amount / Unit price similarity (20%)
            if amt_a > 0 and amt_b > 0:
                amt_diff = abs(amt_a - amt_b) / max(amt_a, amt_b)
                amt_sim = max(0.0, 1.0 - amt_diff)
            else:
                amt_sim = 1.0 if amt_a == amt_b else 0.0

            pair_sim = 0.30 * hsn_match + 0.30 * jaccard + 0.20 * qty_sim + 0.20 * amt_sim
            if pair_sim > best_sim:
                best_sim = pair_sim
                best_b = (desc_b, hsn_b, qty_b, price_b, amt_b)
                best_b_idx = b_idx

        if best_b and best_sim >= 0.55:
            used_b_indices.add(best_b_idx)
            matched_pairs.append({
                "item_a": desc_a,
                "hsn_a": hsn_a,
                "qty_a": qty_a,
                "price_a": price_a,
                "amt_a": amt_a,
                "item_b": best_b[0],
                "hsn_b": best_b[1],
                "qty_b": best_b[2],
                "price_b": best_b[3],
                "amt_b": best_b[4],
                "similarity": round(best_sim, 2),
            })
            total_score += best_sim

    avg_sim = round(total_score / max(len(items_a), 1), 2)
    is_match = (avg_sim >= 0.65) or (len(matched_pairs) >= 2 and avg_sim >= 0.45)
    return {
        "line_item_match": is_match,
        "similarity": avg_sim,
        "matched_items": matched_pairs,
        "total_items_a": len(items_a),
        "total_items_b": len(items_b),
    }


def find_matching_line_items_in_dataset(inv_id: str, candidate_inv_ids: list[str] = None) -> dict:
    """Find the highest line-item match for an invoice among candidate invoices in the dataset."""
    invoices_df = data_store.get("invoices")
    if invoices_df.empty or inv_id not in invoices_df.index:
        return {"line_item_match": False, "similarity": 0.0, "matched_items": [], "matched_invoice_id": None}

    if not candidate_inv_ids:
        # Check other invoices from the same seller or buyer
        target = invoices_df.loc[inv_id]
        # Handle potential DataFrame (duplicate indices)
        if hasattr(target, "iloc") and len(target.shape) > 1:
            target = target.iloc[0]
        
        seller_id = target.get("seller_id")
        buyer_id = target.get("buyer_id")
        
        # Reset index to ensure proper boolean filtering
        invoices_reset = invoices_df.reset_index() if "invoice_id" not in invoices_df.columns else invoices_df
        mask = ((invoices_reset["seller_id"] == seller_id) | (invoices_reset["buyer_id"] == buyer_id))
        mask &= (invoices_reset["invoice_id"] != inv_id)
        candidates = invoices_reset[mask]
        candidate_inv_ids = candidates["invoice_id"].head(25).tolist()

    best_result = {"line_item_match": False, "similarity": 0.0, "matched_items": [], "matched_invoice_id": None}
    for cand_id in candidate_inv_ids:
        res = compare_line_items_between_invoices(inv_id, cand_id)
        if res["similarity"] > best_result["similarity"]:
            best_result = {**res, "matched_invoice_id": cand_id}

    return best_result
