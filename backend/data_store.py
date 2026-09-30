"""
Data store — loads all CSVs once at startup and holds them in memory.
All services query this store rather than reading files on every request.
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path
from config import settings
import logging

log = logging.getLogger(__name__)

_DATA: dict[str, pd.DataFrame] = {}
_FILE_MAP = {
    "companies": "companies.csv",
    "lenders": "lenders.csv",
    "invoices": "invoices.csv",
    "line_items": "invoice_line_items.csv",
    "financing": "financing_records.csv",
    "eway_bills": "eway_bills.csv",
    "payment_history": "payment_history.csv",
    "fraud_labels": "fraud_labels.csv",
    "risk_features": "risk_features.csv",
}


def _reindex_dataframes() -> None:
    if not _DATA.get("invoices", pd.DataFrame()).empty:
        _DATA["invoices"] = _DATA["invoices"].copy()
        _DATA["invoices"].set_index("invoice_id", inplace=True, drop=False)
    if not _DATA.get("companies", pd.DataFrame()).empty:
        _DATA["companies"] = _DATA["companies"].copy()
        _DATA["companies"].set_index("company_id", inplace=True, drop=False)
    if not _DATA.get("fraud_labels", pd.DataFrame()).empty:
        _DATA["fraud_labels"] = _DATA["fraud_labels"].copy()
        _DATA["fraud_labels"].set_index("invoice_id", inplace=True, drop=False)
    if not _DATA.get("risk_features", pd.DataFrame()).empty:
        _DATA["risk_features"] = _DATA["risk_features"].copy()
        _DATA["risk_features"].set_index("invoice_id", inplace=True, drop=False)


def load_all() -> None:
    """Called once on application startup."""
    data_dir: Path = settings.DATA_DIR

    for key, filename in _FILE_MAP.items():
        path = data_dir / filename
        if path.exists():
            _DATA[key] = pd.read_csv(path, low_memory=False)
            log.info(f"Loaded {key}: {len(_DATA[key])} rows")
        else:
            log.warning(f"Missing data file: {filename}")
            _DATA[key] = pd.DataFrame()

    _reindex_dataframes()
    log.info("All data loaded successfully.")


def save_all() -> None:
    data_dir: Path = settings.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    for key, filename in _FILE_MAP.items():
        if key not in _DATA:
            continue
        df = _DATA[key].copy()
        if df.empty:
            continue
        path = data_dir / filename
        # Ensure index does not leak into CSV output for key tables that keep invoice_id/company_id as columns.
        if "invoice_id" in df.columns and "invoice_id" not in ["invoice_id"]:
            pass
        df.to_csv(path, index=False)


def get(key: str) -> pd.DataFrame:
    return _DATA.get(key, pd.DataFrame())
