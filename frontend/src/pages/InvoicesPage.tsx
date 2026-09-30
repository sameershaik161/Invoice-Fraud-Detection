import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getInvoices } from '@/services/api'
import type { InvoiceListItem, RiskLevel } from '@/types'
import { formatCurrency, formatDate } from '@/utils/format'
import { Search, Filter, ArrowUpDown, Plus, ChevronLeft, ChevronRight } from 'lucide-react'
import RiskBadge from '@/components/RiskBadge'
import clsx from 'clsx'

const RISK_FILTERS: Array<RiskLevel | 'ALL'> = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function InvoicesPage() {
  const navigate = useNavigate()
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'ALL'>('ALL')
  const [sortBy, setSortBy] = useState<'invoice_id' | 'invoice_date' | 'net_amount'>('invoice_date')
  const [sortDescending, setSortDescending] = useState(true)
  const [page, setPage] = useState(0)

  useEffect(() => {
    setLoading(true)
    setLoadError(false)
    getInvoices({ limit: 200, risk_level: riskFilter === 'ALL' ? undefined : riskFilter })
      .then(r => setInvoices(r.data))
      .catch(() => { setInvoices([]); setLoadError(true) })
      .finally(() => setLoading(false))
  }, [riskFilter])

  useEffect(() => setPage(0), [search, riskFilter])

  const filtered = search
    ? invoices.filter(i =>
        i.invoice_id.toLowerCase().includes(search.toLowerCase()) ||
        i.seller_name.toLowerCase().includes(search.toLowerCase()) ||
        i.buyer_name.toLowerCase().includes(search.toLowerCase())
      )
    : invoices
  const sorted = useMemo(() => [...filtered].sort((left, right) => {
    const first = left[sortBy]
    const second = right[sortBy]
    const comparison = typeof first === 'number' && typeof second === 'number'
      ? first - second
      : String(first ?? '').localeCompare(String(second ?? ''))
    return sortDescending ? -comparison : comparison
  }), [filtered, sortBy, sortDescending])
  const pageSize = 25
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize))
  const pageRows = sorted.slice(page * pageSize, (page + 1) * pageSize)

  const changeSort = (key: typeof sortBy) => {
    if (sortBy === key) setSortDescending((descending) => !descending)
    else { setSortBy(key); setSortDescending(key === 'invoice_date' || key === 'net_amount') }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-surface-700 pb-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Invoices</h2>
          <p className="mt-1 text-sm text-slate-500">Search invoice records and review risk-engine results</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/invoices/add')}><Plus className="h-4 w-4" /> Add Invoice</button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1 max-w-lg">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            id="invoice-list-search"
            className="input w-full pl-9"
            placeholder="Search invoice ID, seller, buyer..."
            value={search}
            aria-label="Search invoice ID, seller, buyer"
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          {RISK_FILTERS.map(f => (
            <button
              key={f}
              className={clsx(
                'px-3 py-1 rounded text-xs font-semibold transition-all',
                riskFilter === f
                  ? f === 'ALL' ? 'bg-blue-600 text-white'
                    : f === 'CRITICAL' ? 'bg-red-50 text-red-800 ring-1 ring-red-200'
                    : f === 'HIGH' ? 'bg-orange-50 text-orange-800 ring-1 ring-orange-200'
                    : f === 'MEDIUM' ? 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                    : 'bg-green-50 text-green-800 ring-1 ring-green-200'
                  : 'bg-surface-800 text-slate-400 hover:text-slate-200'
              )}
              onClick={() => setRiskFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-600">{filtered.length.toLocaleString()} invoices</span>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table" aria-label="Invoice records">
            <thead>
              <tr>
                <th><button className="inline-flex items-center gap-1" onClick={() => changeSort('invoice_id')}>Invoice ID <ArrowUpDown className="w-3 h-3" /></button></th>
                <th><button className="inline-flex items-center gap-1" onClick={() => changeSort('invoice_date')}>Date <ArrowUpDown className="w-3 h-3" /></button></th>
                <th>Seller</th>
                <th>Buyer</th>
                <th className="text-right"><button className="inline-flex items-center gap-1" onClick={() => changeSort('net_amount')}>Amount <ArrowUpDown className="w-3 h-3" /></button></th>
                <th>Risk</th>
                <th>Lenders</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && Array.from({ length: 6 }, (_, index) => <tr key={`loading-${index}`} aria-hidden="true"><td colSpan={8}><div className="h-4 animate-pulse rounded bg-surface-700" /></td></tr>)}
              {!loading && loadError && <tr><td colSpan={8} className="py-12 text-center text-sm text-red-700">Unable to load invoices. Check the API connection and retry.</td></tr>}
              {!loading && pageRows.map(inv => (
                <tr key={inv.invoice_id} onClick={() => navigate(`/investigation/${inv.invoice_id}`)} onKeyDown={(event) => { if (event.key === 'Enter') navigate(`/investigation/${inv.invoice_id}`) }} tabIndex={0}>
                  <td className="font-mono text-blue-400 text-xs">{inv.invoice_id}</td>
                  <td className="text-slate-400 text-xs">{formatDate(inv.invoice_date)}</td>
                  <td className="max-w-[140px] truncate">{inv.seller_name}</td>
                  <td className="max-w-[140px] truncate">{inv.buyer_name}</td>
                  <td className="text-right font-mono text-xs">{formatCurrency(inv.net_amount)}</td>
                  <td><RiskBadge level={inv.risk_level} showIcon={false} size="sm" /></td>
                  <td><span className={clsx('font-mono text-xs font-semibold', (inv.lender_count ?? 0) > 1 ? 'text-red-700' : 'text-slate-600')}>{inv.lender_count ?? 'Not available'}</span></td>
                  <td>
                    <button
                      className="text-[10px] text-blue-500 hover:text-blue-400"
                      onClick={e => { e.stopPropagation(); navigate(`/verify?id=${inv.invoice_id}`) }}
                    >
                      Investigate →
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && !loadError && filtered.length === 0 && (
                <tr><td colSpan={8} className="py-12 text-center text-slate-500">No invoices match the current search and risk filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {!loading && !loadError && filtered.length > 0 && <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-700 px-4 py-3 text-xs text-slate-600">
          <span>Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, filtered.length)} of {filtered.length.toLocaleString()}</span>
          <div className="flex items-center gap-2">
            <button className="btn-ghost px-2 py-1" aria-label="Previous page" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0}><ChevronLeft className="h-4 w-4" />Previous</button>
            <span>Page {page + 1} of {pageCount}</span>
            <button className="btn-ghost px-2 py-1" aria-label="Next page" onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))} disabled={page >= pageCount - 1}>Next<ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>}
      </div>
    </div>
  )
}
