// Core domain types matching backend Pydantic schemas

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type RecommendedAction = 'PROCEED' | 'MANUAL_REVIEW' | 'ENHANCED_VERIFICATION' | 'HOLD_PAYOUT'

export interface LineItem {
  line_no: number
  item_description: string
  quantity: number
  unit_price: number
  line_total: number
}

export interface FinancingRecord {
  financing_id: string
  lender_id: string
  lender_name: string
  lender_type: string
  application_date: string
  financed_amount: number
  status: string
  product_type: string
}

export interface EWayBill {
  eway_bill_no: string
  seller_gstin: string
  buyer_gstin: string
  origin_state: string
  destination_state: string
  delivery_status: string
  movement_date: string
  transporter_id: string
  delivery_proof_hash: string
}

export interface InvoiceDetail {
  invoice_id: string
  invoice_date: string
  due_date: string
  net_amount: number
  currency: string
  primary_line_item: string
  line_item_count: number
  seller_id: string
  seller_name: string
  seller_gstin: string
  seller_state: string
  seller_industry: string
  buyer_id: string
  buyer_name: string
  buyer_gstin: string
  buyer_state: string
  buyer_industry: string
  line_items: LineItem[]
  financing_records: FinancingRecord[]
  eway_bill?: EWayBill
  ground_truth_label?: string
}

export interface InvoiceListItem {
  invoice_id: string
  invoice_date: string
  net_amount: number
  seller_name: string
  buyer_name: string
  risk_level?: RiskLevel
  risk_score?: number
  lender_count?: number
}

export interface RiskSignal {
  signal_id: string
  name: string
  description: string
  weight: number
  triggered: boolean
  value?: string
}

export interface EvidenceItem {
  step: number
  title: string
  detail: string
  severity: 'critical' | 'warning' | 'info' | 'safe'
}

export interface AuditEntry {
  timestamp: string
  event: string
  detail: string
  level: 'info' | 'warning' | 'error' | 'success'
}

export interface VerificationResult {
  invoice_id: string
  risk_score: number
  risk_level: RiskLevel
  recommended_action: RecommendedAction
  confidence: number
  lender_count: number
  duplicate_detected: boolean
  verification_time_ms: number
  signals: RiskSignal[]
  evidence: EvidenceItem[]
  audit_trail: AuditEntry[]
  summary: string
}

export interface GraphNode {
  id: string
  label: string
  type: 'invoice' | 'company' | 'lender' | 'eway'
  properties: Record<string, string>
  risk_flag: boolean
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  properties: Record<string, string>
  highlighted: boolean
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  suspicious_node_ids: string[]
  suspicious_edge_ids: string[]
}

export interface Lender {
  lender_id: string
  lender_name: string
  lender_type: string
  total_invoices: number
  total_exposure: number
  high_risk_count: number
  duplicate_attempts: number
}

export interface Overview {
  total_invoices: number
  verified_today: number | null
  high_risk_invoices: number
  critical_invoices: number
  potential_exposure: number
  lenders_connected: number
  detection_rate: number | null
  double_financing_count: number
}

export interface Analytics {
  risk_distribution: Array<{ level: string; count: number }>
  financing_by_lender: Array<{ lender: string; amount: number }>
  industry_risk: Array<{ industry: string; avg_risk: number }>
  monthly_duplicates: Array<{ month: string; count: number }>
  top_risk_sellers: Array<{ name: string; avg_risk: number }>
  top_risk_buyers: Array<{ name: string; avg_risk: number }>
  amount_by_risk: Array<{ level: string; amount_cr: number }>
}

export interface SearchResultItem {
  id: string
  label: string
  type: 'INVOICES' | 'COMPANIES' | 'LENDERS' | 'DELIVERY PROOFS'
  subtitle: string
  route: string
}

export interface AlertItem {
  invoice_id: string
  level: RiskLevel | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  risk_score: number
  title: string
  message: string
  route: string
  timestamp: string
}

export interface TimelineEvent {
  date: string
  label: string
  detail: string
  severity: 'info' | 'warning' | 'success'
}

export interface InvestigationData {
  invoice_id: string
  invoice: InvoiceDetail
  risk: VerificationResult
  graph: GraphResponse
  timeline: TimelineEvent[]
  evidence: EvidenceItem[]
  status: string
}

export interface CopilotEvidence {
  ref_id?: string
  source_type?: string
  source_id?: string
  tool?: string
  timestamp?: string
  confidence?: number
  href?: string
  title?: string
  detail?: string
  severity?: string
}

export interface CopilotFinding {
  kind: string
  title: string
  detail: string
  value?: unknown
  evidence_refs?: string[]
}

export interface CopilotEntity {
  type: string
  id: string
  label: string
  href: string
}

export interface CopilotAction {
  label: string
  href: string
}

export interface CopilotResponse {
  answer: string
  intents: string[]
  tools: string[]
  findings: CopilotFinding[]
  entities: CopilotEntity[]
  evidence: CopilotEvidence[]
  citations?: Array<{ id: string; source_type?: string; source_id?: string; href?: string }>
  actions: CopilotAction[]
  report_text?: string | null
  invoice_id?: string | null
  llm_used: boolean
  provider?: string
  planner_provider?: string | null
  fallback_reason?: string | null
  latency_ms: number
  tool_latency_ms?: number
  llm_latency_ms?: number
}

export interface CopilotStatus {
  configured: boolean
  provider: string
  fallback_providers: string[]
  mode: 'AI' | 'Evidence Mode'
}
