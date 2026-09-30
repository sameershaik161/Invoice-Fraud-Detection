import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Play, CheckCircle2, Loader2, AlertTriangle,
  Shield, ChevronDown, ChevronUp, GitBranch, Clock, Info,
  XCircle, TrendingUp, UploadCloud, X, Sparkles
} from 'lucide-react'
import { verifyInvoice, getDemoInvoice, submitMSMEDispute } from '@/services/api'
import type { VerificationResult, RiskLevel } from '@/types'
import RiskMeter from '@/components/RiskMeter'
import RiskBadge from '@/components/RiskBadge'
import { getActionColor, getActionLabel } from '@/utils/format'
import clsx from 'clsx'

const VERIFY_STEPS = [
  'Checking invoice identity…',
  'Verifying seller & buyer GSTIN…',
  'Checking financing history…',
  'Running similarity analysis…',
  'Checking delivery proof…',
  'Computing risk score…',
  'Generating evidence trail…',
]

type VerifyState = 'idle' | 'loading' | 'done' | 'error'

export default function VerifyPage() {
  const [searchParams] = useSearchParams()
  const { id: paramId } = useParams()
  const navigate = useNavigate()
  const [invoiceId, setInvoiceId] = useState(paramId ?? searchParams.get('id') ?? '')
  const [demoId, setDemoId] = useState('INV-2026-02970')
  const [state, setState] = useState<VerifyState>('idle')
  const [stepIdx, setStepIdx] = useState(0)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showEvidence, setShowEvidence] = useState(true)
  const [showAudit, setShowAudit] = useState(false)
  const [showDisputeModal, setShowDisputeModal] = useState(false)
  const [disputeReason, setDisputeReason] = useState('')
  const [supplierNotes, setSupplierNotes] = useState('')
  const [ewayNo, setEwayNo] = useState('')
  const [evidenceFile, setEvidenceFile] = useState('')
  const [disputeStatus, setDisputeStatus] = useState<string | null>(null)
  const [disputeSubmitting, setDisputeSubmitting] = useState(false)
  const stepTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    getDemoInvoice().then(r => setDemoId(r.data.demo_invoice_id)).catch(() => {})
  }, [])

  useEffect(() => {
    const id = paramId || searchParams.get('id')
    if (id) {
      setInvoiceId(id)
    }
  }, [paramId, searchParams])


  const handleVerify = async () => {
    if (!invoiceId.trim()) return
    setState('loading')
    setStepIdx(0)
    setResult(null)
    setError(null)

    // Animate steps
    let idx = 0
    stepTimer.current = setInterval(() => {
      idx++
      setStepIdx(idx)
      if (idx >= VERIFY_STEPS.length - 1) {
        clearInterval(stepTimer.current!)
      }
    }, 340)

    try {
      const res = await verifyInvoice(invoiceId.trim())
      if (stepTimer.current) clearInterval(stepTimer.current)
      setStepIdx(VERIFY_STEPS.length)
      setResult(res.data)
      setState('done')
    } catch (e: unknown) {
      if (stepTimer.current) clearInterval(stepTimer.current)
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setError(err?.response?.data?.detail ?? err?.message ?? 'Verification failed')
      setState('error')
    }
  }

  const handleSubmitDispute = async () => {
    if (!invoiceId.trim() || !disputeReason.trim()) return
    setDisputeSubmitting(true)
    setDisputeStatus(null)
    try {
      const res = await submitMSMEDispute(invoiceId.trim(), {
        dispute_reason: disputeReason.trim(),
        supplier_notes: supplierNotes.trim() || undefined,
        eway_bill_no: ewayNo.trim() || undefined,
        evidence_document_name: evidenceFile.trim() || undefined,
      })
      const result = res.data
      setDisputeStatus([
        `Result: ${result.status}`,
        `Invoice: ${result.canonical_invoice_id ?? result.invoice_id}`,
        `Verification status: ${result.verification_status}`,
        `Timestamp: ${result.timestamp}`,
        `Gateway: ${result.gateway_status}`,
        result.message,
      ].join('\n'))
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setDisputeStatus(err?.response?.data?.detail ?? err?.message ?? 'Submission failed')
    } finally {
      setDisputeSubmitting(false)
    }
  }

  useEffect(() => {
    if (invoiceId && searchParams.get('id')) {
      handleVerify()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const riskLevelColors: Record<RiskLevel, string> = {
    LOW: 'text-green-400',
    MEDIUM: 'text-amber-400',
    HIGH: 'text-red-400',
    CRITICAL: 'text-red-300',
  }

  const evidenceClass = (sev: string) => {
    switch (sev) {
      case 'critical': return 'evidence-critical'
      case 'warning': return 'evidence-warning'
      case 'safe': return 'evidence-safe'
      default: return 'evidence-info'
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="border-b border-surface-700 pb-4">
        <h2 className="text-2xl font-semibold text-slate-900">Invoice Verification</h2>
        <p className="mt-1 text-sm text-slate-500">
          Multi-signal risk analysis — explainable evidence for every decision
        </p>
      </div>

      {/* Search bar */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="verify-invoice-input"
                className="input w-full pl-9 font-mono text-sm"
                aria-label="Invoice ID to verify"
                placeholder="Enter Invoice ID (e.g. INV-2026-02970)"
                value={invoiceId}
                onChange={e => setInvoiceId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleVerify()}
                disabled={state === 'loading'}
              />
            </div>
            <button
              id="btn-run-verification"
              className="btn-primary"
              onClick={handleVerify}
              disabled={state === 'loading' || !invoiceId.trim()}
            >
              {state === 'loading'
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Play className="w-4 h-4" />}
              {state === 'loading' ? 'Verifying…' : 'Verify Invoice'}
            </button>
            <button
              id="btn-load-demo-verify"
              className="btn-ghost"
              onClick={() => { setInvoiceId(demoId) }}
              disabled={state === 'loading'}
            >
              Demo
            </button>
            <button
              className="btn-ghost"
              onClick={() => { setDisputeStatus(null); setShowDisputeModal(true) }}
              disabled={state === 'loading' || !invoiceId.trim()}
            >
              <UploadCloud className="w-4 h-4" />
              MSME Evidence
            </button>
          </div>
        </div>
      </div>

      {/* Loading steps */}
      <AnimatePresence>
        {state === 'loading' && (
          <motion.div
            className="card"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="card-header">
              <span className="text-sm font-medium text-slate-300 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                Running verification for{' '}
                <span className="font-mono text-blue-400">{invoiceId}</span>
              </span>
            </div>
            <div className="card-body space-y-0">
              {VERIFY_STEPS.map((step, i) => (
                <div key={step} className="step-row">
                  {i < stepIdx ? (
                    <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                  ) : i === stepIdx ? (
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-surface-600 flex-shrink-0" />
                  )}
                  <span className={clsx('text-sm', i < stepIdx
                    ? 'text-slate-400 line-through decoration-surface-600'
                    : i === stepIdx ? 'text-slate-200' : 'text-slate-600'
                  )}>
                    {step}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error state */}
      {state === 'error' && (
        <div role="alert" className="card border-red-200 bg-red-50">
          <div className="card-body flex flex-wrap items-center gap-3">
            <XCircle className="h-5 w-5 flex-shrink-0 text-red-800" />
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-red-900">Invoice could not be verified</div>
              <div className="mt-0.5 break-words text-sm text-red-800">{error}</div>
            </div>
            <button className="btn-ghost" onClick={handleVerify}>Retry</button>
          </div>
        </div>
      )}

      {state === 'idle' && <div className="card border-blue-100">
        <div className="card-body flex items-start gap-3">
          <Shield className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-800" />
          <div><div className="text-sm font-semibold text-slate-900">Ready to verify</div><p className="mt-1 text-sm text-slate-600">Enter an invoice ID to begin evidence-based verification. Risk scores and findings are returned by the verification service.</p></div>
        </div>
      </div>}

      {/* Result */}
      <AnimatePresence>
        {state === 'done' && result && (
          <motion.div
            className="space-y-4"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {/* Main result card */}
            <div className={clsx('card border', result.risk_level === 'CRITICAL' || result.risk_level === 'HIGH'
              ? 'border-red-800/60 glow-red' : 'border-green-800/40')}>
              <div className="card-body">
                <div className="flex flex-col items-start gap-6 md:flex-row md:gap-8">
                  {/* Score gauge */}
                  <div className="flex flex-col items-center">
                    <RiskMeter score={result.risk_score} level={result.risk_level} size="lg" />
                    <div className="mt-3">
                      <RiskBadge level={result.risk_level} size="lg" />
                    </div>
                  </div>

                  {/* Summary */}
                  <div className="flex-1 space-y-4">
                    <div>
                      <div className={clsx('text-2xl font-bold', riskLevelColors[result.risk_level])}>
                        {result.duplicate_detected ? 'DOUBLE-FINANCING DETECTED' : 'No Duplicate Detected'}
                      </div>
                      <div className="text-sm text-slate-400 mt-1 font-mono">{result.invoice_id}</div>
                    </div>

                    {/* Recommended action */}
                    <div className="bg-surface-800 rounded-md px-4 py-3">
                      <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">Recommended Action</div>
                      <div className={clsx('text-lg font-bold', getActionColor(result.recommended_action))}>
                        {getActionLabel(result.recommended_action).toUpperCase()}
                      </div>
                    </div>

                    {/* Stats row */}
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <div className="stat-label">Lenders Involved</div>
                        <div className={clsx('text-xl font-bold mt-1',
                          result.lender_count > 1 ? 'text-red-400' : 'text-green-400')}>
                          {result.lender_count}
                        </div>
                      </div>
                      <div>
                        <div className="stat-label">Confidence</div>
                        <div className="text-xl font-bold text-slate-200 mt-1">
                          {(result.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <div className="stat-label">Verification Time</div>
                        <div className="text-xl font-bold text-slate-200 mt-1 font-mono text-sm leading-loose">
                          {result.verification_time_ms}ms
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Signals */}
            <div className="card">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-slate-400" />
                  <span className="text-sm font-semibold text-slate-200">Risk Signals</span>
                </div>
              </div>
              <div className="card-body space-y-2">
                {result.signals.map(sig => (
                  <div key={sig.signal_id} className="flex items-center gap-3 py-2 border-b border-surface-800 last:border-0">
                    {sig.triggered
                      ? <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      : <CheckCircle2 className="w-4 h-4 text-green-500/60 flex-shrink-0" />
                    }
                    <div className="flex-1">
                      <div className={clsx('text-sm font-medium', sig.triggered ? 'text-slate-200' : 'text-slate-500')}>
                        {sig.name}
                      </div>
                      <div className="text-xs text-slate-600 mt-0.5">{sig.description}</div>
                    </div>
                    {sig.value && (
                      <span className="text-xs font-mono text-slate-400 bg-surface-800 px-2 py-0.5 rounded">
                        {sig.value}
                      </span>
                    )}
                    {sig.triggered && (
                      <span className="text-xs font-bold text-red-400">+{sig.weight}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Evidence — collapsible */}
            <div className="card">
              <button
                className="card-header w-full text-left"
                onClick={() => setShowEvidence(v => !v)}
                aria-expanded={showEvidence}
              >
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-slate-400" />
                  <span className="text-sm font-semibold text-slate-200">Why was this flagged?</span>
                  <span className="badge-info ml-2">{result.evidence.length} findings</span>
                </div>
                {showEvidence
                  ? <ChevronUp className="w-4 h-4 text-slate-500" />
                  : <ChevronDown className="w-4 h-4 text-slate-500" />}
              </button>
              <AnimatePresence>
                {showEvidence && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="card-body space-y-3">
                      {result.evidence.map(ev => (
                        <div key={ev.step} className={evidenceClass(ev.severity)}>
                          <div className="flex items-start gap-2">
                            <span className="text-xs font-bold text-slate-500 mt-0.5 font-mono">{ev.step}.</span>
                            <div>
                              <div className="text-sm font-semibold text-slate-200">{ev.title}</div>
                              <div className="text-xs text-slate-400 mt-1 leading-relaxed">{ev.detail}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Quick actions */}
            <div className="flex flex-wrap gap-3">
              <button
                className="btn-ghost"
                onClick={() => navigate(`/graph?id=${result.invoice_id}`)}
              >
                <GitBranch className="w-4 h-4" />
                View Graph
              </button>
              <button
                className="btn-ghost"
                onClick={() => setShowAudit(v => !v)}
              >
                <Clock className="w-4 h-4" />
                Audit Trail
              </button>
              <button
                className="btn-ghost"
                onClick={() => navigate(`/invoices/${result.invoice_id}`)}
              >
                <Info className="w-4 h-4" />
                Invoice Detail
              </button>
              <button
                className="btn-ghost"
                onClick={() => navigate(`/copilot?invoiceId=${encodeURIComponent(result.invoice_id)}`)}
              >
                <Sparkles className="w-4 h-4" />
                Ask Copilot
              </button>
            </div>

            {/* Audit trail — collapsible */}
            <AnimatePresence>
              {showAudit && (
                <motion.div
                  className="card"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <div className="card-header">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-slate-400" />
                      <span className="text-sm font-semibold text-slate-200">Audit Trail</span>
                    </div>
                  </div>
                  <div className="card-body">
                    <div className="space-y-2">
                      {result.audit_trail.map((entry, i) => (
                        <div key={i} className="flex items-start gap-3 py-1.5 border-b border-surface-800 last:border-0">
                          <span className="font-mono text-xs text-slate-600 flex-shrink-0 w-20">
                            {entry.timestamp}
                          </span>
                          <div className="flex-1">
                            <span className={clsx(
                              'text-xs font-semibold',
                              entry.level === 'warning' ? 'text-amber-400'
                              : entry.level === 'error' ? 'text-red-400'
                              : entry.level === 'success' ? 'text-green-400'
                              : 'text-slate-400'
                            )}>
                              {entry.event}
                            </span>
                            <span className="text-xs text-slate-600 ml-2">{entry.detail}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {showDisputeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="msme-dialog-title"
            className="card w-full max-w-xl max-h-[90vh] overflow-y-auto"
          >
            <div className="card-header flex items-center justify-between">
              <div>
                <h3 id="msme-dialog-title" className="text-base font-semibold text-slate-100">MSME Dispute &amp; Verification</h3>
                <p className="mt-1 text-xs text-slate-500">Invoice: <span className="font-mono">{invoiceId.trim()}</span></p>
              </div>
              <button className="btn-ghost" onClick={() => setShowDisputeModal(false)} aria-label="Close MSME verification">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="card-body space-y-4">
              <div className="border border-amber-800/50 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
                SIMULATED / DEMO MODE. No live GSTN or e-Way Bill verification is performed.
              </div>
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-400">Dispute reason</span>
                <textarea className="input min-h-20 w-full" value={disputeReason} onChange={e => setDisputeReason(e.target.value)} required />
              </label>
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-400">Supplier notes</span>
                <textarea className="input min-h-16 w-full" value={supplierNotes} onChange={e => setSupplierNotes(e.target.value)} />
              </label>
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-400">e-Way Bill number</span>
                <input className="input w-full font-mono" value={ewayNo} onChange={e => setEwayNo(e.target.value)} />
              </label>
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-400">Evidence document name</span>
                <input className="input w-full" value={evidenceFile} onChange={e => setEvidenceFile(e.target.value)} placeholder="Enter the submitted evidence document name" />
              </label>
              <div className="flex justify-end gap-2">
                <button className="btn-ghost" onClick={() => setShowDisputeModal(false)}>Cancel</button>
                <button className="btn-primary" onClick={handleSubmitDispute} disabled={disputeSubmitting || !disputeReason.trim()}>
                  {disputeSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                  Submit Evidence
                </button>
              </div>
              {disputeStatus && (
                <pre role="status" className="whitespace-pre-wrap break-words border border-surface-700 bg-surface-900 p-3 text-xs text-slate-300">{disputeStatus}</pre>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
