import { useState } from 'react'
import { verifyInvoice } from '@/services/api'
import type { AuditEntry } from '@/types'
import { ScrollText, Loader2, Search } from 'lucide-react'
import clsx from 'clsx'

const LEVEL_COLORS: Record<string, string> = {
  info: 'text-blue-400',
  warning: 'text-amber-400',
  error: 'text-red-400',
  success: 'text-green-400',
}

const LEVEL_DOT: Record<string, string> = {
  info: 'bg-blue-400',
  warning: 'bg-amber-400',
  error: 'bg-red-400',
  success: 'bg-green-400',
}

export default function AuditPage() {
  const [invoiceId, setInvoiceId] = useState('')
  const [trail, setTrail] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')

  const handleLoad = async () => {
    if (!invoiceId.trim()) return
    setLoading(true)
    setError('')
    setLoaded(false)
    try {
      const res = await verifyInvoice(invoiceId.trim())
      setTrail(res.data.audit_trail)
      setLoaded(true)
    } catch {
      setTrail([])
      setLoaded(true)
      setError('Audit trail could not be loaded. Verify the invoice ID and retry.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="border-b border-surface-700 pb-4">
        <h2 className="text-2xl font-semibold text-slate-900">Audit Trail</h2>
        <p className="mt-1 text-sm text-slate-500">Recorded verification events for an invoice</p>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                className="input w-full pl-9 font-mono"
                aria-label="Invoice ID for audit trail"
                placeholder="Invoice ID"
                value={invoiceId}
                onChange={e => setInvoiceId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLoad()}
              />
            </div>
            <button className="btn-primary" onClick={handleLoad} disabled={loading || !invoiceId.trim()}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScrollText className="w-4 h-4" />}
              Load Audit
            </button>
          </div>
        </div>
      </div>

      {loaded && !error && trail.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-semibold text-slate-200">
                Audit Trail · {invoiceId}
              </span>
            </div>
            <span className="text-xs text-slate-500">{trail.length} events</span>
          </div>
          <div className="card-body">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-[88px] top-0 bottom-0 w-px bg-surface-700" />

              <div className="space-y-0">
                {trail.map((entry, i) => (
                  <div key={i} className="flex items-start gap-4 py-3 relative">
                    {/* Time */}
                    <span className="font-mono text-xs text-slate-600 w-20 flex-shrink-0 pt-0.5">
                      {entry.timestamp}
                    </span>
                    {/* Dot */}
                    <div className={clsx(
                      'w-2 h-2 rounded-full flex-shrink-0 mt-1.5 z-10',
                      LEVEL_DOT[entry.level] ?? 'bg-slate-600'
                    )} />
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className={clsx('text-sm font-medium', LEVEL_COLORS[entry.level] ?? 'text-slate-400')}>
                        {entry.event}
                      </div>
                      {entry.detail && (
                        <div className="text-xs text-slate-600 mt-0.5">{entry.detail}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {error && <div role="alert" className="card border-red-200 p-5">
        <div className="text-sm font-semibold text-red-800">Unable to load audit trail</div>
        <p className="mt-1 text-sm text-slate-600">{error}</p>
        <button className="btn-ghost mt-3" onClick={handleLoad} disabled={loading}>Retry</button>
      </div>}

      {loaded && !error && trail.length === 0 && <div className="card p-5 text-sm text-slate-600">No audit events were returned for this invoice.</div>}

      {!loaded && !loading && !error && (
        <div className="card">
          <div className="card-body flex flex-col items-center justify-center py-12 text-slate-600">
            <ScrollText className="mb-3 h-7 w-7 text-blue-800" />
            <p className="text-sm">Enter an invoice ID to view the verification audit trail.</p>
          </div>
        </div>
      )}
    </div>
  )
}
