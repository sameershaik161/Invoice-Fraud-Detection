import axios from 'axios'
import type {
  InvoiceDetail,
  InvoiceListItem,
  VerificationResult,
  GraphResponse,
  Lender,
  Overview,
  Analytics,
  CopilotResponse,
  CopilotStatus,
} from '@/types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
})

export interface SystemHealthStatus {
  status: string
  app: string
  version: string
  data_loaded: boolean
  neo4j_enabled: boolean
}

// Health
export const getHealth = () => api.get<SystemHealthStatus>('/health')

// Demo
export const getDemoInvoice = () => api.get<{ demo_invoice_id: string }>('/demo/invoice')

// Invoices
export const getInvoices = (params?: {
  limit?: number
  offset?: number
  risk_level?: string
  search?: string
}) => api.get<InvoiceListItem[]>('/invoices', { params })

export const checkDuplicateInvoice = (payload: any) =>
  api.post('/invoices/check-duplicate', payload)

export const createInvoice = (payload: any) =>
  api.post('/invoices', payload)

export const getInvoice = (id: string) => api.get<InvoiceDetail>(`/invoices/${id}`)

export const getInvoiceEvidence = (id: string) =>
  api.get<{ invoice_id: string; evidence: any[] }>(`/invoices/${id}/evidence`)

export const getInvoiceTimeline = (id: string) =>
  api.get<{ invoice_id: string; events: any[] }>(`/invoices/${id}/timeline`)

// Verification
export const verifyInvoice = (id: string) =>
  api.post<VerificationResult>(`/invoices/${id}/verify`)

export const getInvoiceRisk = (id: string) =>
  api.get<VerificationResult>(`/invoices/${id}/risk`)

export const getInvoiceGraph = (id: string) =>
  api.get<GraphResponse>(`/invoices/${id}/graph`)

// Search and investigation
export const getGlobalSearch = (q: string) =>
  api.get<{ query: string; results: any[] }>(`/search`, { params: { q } })

export const getInvestigation = (id: string) =>
  api.get<any>(`/investigation/${id}`)

export const getAlerts = () => api.get<any[]>('/alerts')

export const postCopilotChat = (data: {
  message: string
  invoice_id?: string
  context_entity_id?: string
  context_entity_type?: 'invoice' | 'company' | 'lender' | 'gstin'
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}) => api.post<CopilotResponse>('/copilot/chat', data)

export const getCopilotStatus = () => api.get<CopilotStatus>('/copilot/status')

// Lenders
export const getLenders = () => api.get<Lender[]>('/lenders')

// Analytics
export const getOverview = () => api.get<Overview>('/analytics/overview')
export const getAnalytics = () => api.get<Analytics>('/analytics/charts')

// MSME Dispute Pathway
export const submitMSMEDispute = (
  id: string,
  data: {
    dispute_reason: string
    supplier_notes?: string
    eway_bill_no?: string
    evidence_document_name?: string
  }
) => api.post(`/invoices/${id}/dispute`, data)

// SEC EDGAR Adapter
export const getSECFilings = (companyId: string) =>
  api.get(`/sec/filings/${companyId}`)

