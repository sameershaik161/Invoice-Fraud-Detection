import { useEffect, useState } from 'react'
import { getInvoices } from '@/services/api'
import type { InvoiceListItem } from '@/types'
import { AlertTriangle, AlertOctagon, Clock, Sparkles } from 'lucide-react'
import RiskBadge from '@/components/RiskBadge'
import { formatCurrency, formatDate } from '@/utils/format'
import { useNavigate } from 'react-router-dom'

export default function RiskMonitorPage() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getInvoices({ limit: 200 })
      .then(r => {
        const high = r.data.filter(i =>
          i.risk_level === 'HIGH' || i.risk_level === 'CRITICAL' || (i.lender_count ?? 0) > 1
        )
        setInvoices(high)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const critical = invoices.filter(i => i.risk_level === 'CRITICAL')
  const high = invoices.filter(i => i.risk_level === 'HIGH')
  const duplicate = invoices.filter(i => (i.lender_count ?? 0) > 1)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Risk Monitor</h2>
          <p className="text-sm text-slate-500">High-risk and critical invoices requiring immediate attention</p>
        </div>
        <button className="btn-ghost" onClick={() => navigate('/copilot')}>
          <Sparkles className="h-4 w-4" /> Ask Copilot
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="kpi-card border-red-800/40">
          <div className="flex items-center justify-between mb-2">
            <span className="stat-label">Critical</span>
            <AlertOctagon className="w-4 h-4 text-red-400" />
          </div>
          <div className="stat-value text-red-400">{critical.length}</div>
        </div>
        <div className="kpi-card border-red-800/30">
          <div className="flex items-center justify-between mb-2">
            <span className="stat-label">High Risk</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="stat-value text-amber-400">{high.length}</div>
        </div>
        <div className="kpi-card border-amber-800/30">
          <div className="flex items-center justify-between mb-2">
            <span className="stat-label">Duplicate Financing</span>
            <Clock className="w-4 h-4 text-orange-400" />
          </div>
          <div className="stat-value text-orange-400">{duplicate.length}</div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="card-header">
          <span className="text-sm font-semibold text-slate-200">
            High-Risk Invoice Queue
          </span>
          <span className="badge-high">{invoices.length} flagged</span>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice ID</th>
                <th>Date</th>
                <th>Seller</th>
                <th>Buyer</th>
                <th className="text-right">Amount</th>
                <th>Risk</th>
                <th>Score</th>
                <th>Lenders</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} className="text-center text-slate-600 py-12">Loading…</td></tr>
              )}
              {!loading && invoices.map(inv => (
                <tr key={inv.invoice_id} onClick={() => navigate(`/verify?id=${inv.invoice_id}`)}>
                  <td className="font-mono text-blue-400 text-xs">{inv.invoice_id}</td>
                  <td className="text-slate-400 text-xs">{formatDate(inv.invoice_date)}</td>
                  <td className="max-w-[120px] truncate">{inv.seller_name}</td>
                  <td className="max-w-[120px] truncate">{inv.buyer_name}</td>
                  <td className="text-right font-mono text-xs">{formatCurrency(inv.net_amount)}</td>
                  <td><RiskBadge level={inv.risk_level} showIcon={false} size="sm" /></td>
                  <td className="font-mono font-bold text-xs">
                    {inv.risk_score !== undefined ? (
                      <span style={{
                        color: (inv.risk_score ?? 0) >= 80 ? '#dc2626'
                          : (inv.risk_score ?? 0) >= 60 ? '#ef4444'
                          : '#f59e0b'
                      }}>
                        {inv.risk_score}/100
                      </span>
                    ) : '—'}
                  </td>
                  <td>
                    <span className={`font-mono text-xs font-bold ${(inv.lender_count ?? 0) > 1 ? 'text-red-400' : 'text-slate-500'}`}>
                      {inv.lender_count ?? 1}
                    </span>
                  </td>
                  <td>
                    <button
                      className="text-[10px] text-blue-500 hover:text-blue-400"
                      onClick={e => { e.stopPropagation(); navigate(`/verify?id=${inv.invoice_id}`) }}
                    >
                      Verify →
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && invoices.length === 0 && (
                <tr><td colSpan={9} className="text-center text-slate-600 py-12">No high-risk invoices found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
