from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendedAction(str, Enum):
    PROCEED = "PROCEED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ENHANCED_VERIFICATION = "ENHANCED_VERIFICATION"
    HOLD_PAYOUT = "HOLD_PAYOUT"


class LineItemSchema(BaseModel):
    line_no: int
    item_description: str
    quantity: float
    unit_price: float
    line_total: float


class FinancingRecordSchema(BaseModel):
    financing_id: str
    lender_id: str
    lender_name: str
    lender_type: str
    application_date: str
    financed_amount: float
    status: str
    product_type: str


class EWayBillSchema(BaseModel):
    eway_bill_no: str
    seller_gstin: str
    buyer_gstin: str
    origin_state: str
    destination_state: str
    delivery_status: str
    movement_date: str
    transporter_id: str
    delivery_proof_hash: str


class InvoiceDetailSchema(BaseModel):
    invoice_id: str
    invoice_date: str
    due_date: str
    net_amount: float
    currency: str
    primary_line_item: str
    line_item_count: int
    seller_id: str
    seller_name: str
    seller_gstin: str
    seller_state: str
    seller_industry: str
    buyer_id: str
    buyer_name: str
    buyer_gstin: str
    buyer_state: str
    buyer_industry: str
    line_items: List[LineItemSchema] = []
    financing_records: List[FinancingRecordSchema] = []
    eway_bill: Optional[EWayBillSchema] = None
    ground_truth_label: Optional[str] = None


class InvoiceListItemSchema(BaseModel):
    invoice_id: str
    invoice_date: str
    net_amount: float
    seller_name: str
    buyer_name: str
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    lender_count: Optional[int] = None


class RiskSignalSchema(BaseModel):
    signal_id: str
    name: str
    description: str
    weight: int
    triggered: bool
    value: Optional[str] = None


class EvidenceItemSchema(BaseModel):
    step: int
    title: str
    detail: str
    severity: str  # "critical" | "warning" | "info" | "safe"


class AuditEntrySchema(BaseModel):
    timestamp: str
    event: str
    detail: str
    level: str  # "info" | "warning" | "error" | "success"


class VerificationResultSchema(BaseModel):
    invoice_id: str
    risk_score: int
    risk_level: RiskLevel
    recommended_action: RecommendedAction
    confidence: float
    lender_count: int
    duplicate_detected: bool
    verification_time_ms: float
    signals: List[RiskSignalSchema]
    evidence: List[EvidenceItemSchema]
    audit_trail: List[AuditEntrySchema]
    summary: str


class GraphNodeSchema(BaseModel):
    id: str
    label: str
    type: str  # "invoice" | "company" | "lender" | "eway"
    properties: dict
    risk_flag: bool = False


class GraphEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    label: str
    properties: dict = {}
    highlighted: bool = False


class GraphResponseSchema(BaseModel):
    nodes: List[GraphNodeSchema]
    edges: List[GraphEdgeSchema]
    suspicious_node_ids: List[str] = []
    suspicious_edge_ids: List[str] = []


class LenderSchema(BaseModel):
    lender_id: str
    lender_name: str
    lender_type: str
    total_invoices: int
    total_exposure: float
    high_risk_count: int
    duplicate_attempts: int


class OverviewSchema(BaseModel):
    total_invoices: int
    verified_today: int | None
    high_risk_invoices: int
    critical_invoices: int
    potential_exposure: float
    lenders_connected: int
    detection_rate: float | None
    double_financing_count: int


class AnalyticsSchema(BaseModel):
    risk_distribution: List[dict]
    financing_by_lender: List[dict]
    industry_risk: List[dict]
    monthly_duplicates: List[dict]
    top_risk_sellers: List[dict]
    top_risk_buyers: List[dict]
    amount_by_risk: List[dict]
