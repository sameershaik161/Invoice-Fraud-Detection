import { useEffect, useMemo, useState } from 'react'
import { getLenders } from '@/services/api'
import type { Lender } from '@/types'
import { formatCurrency } from '@/utils/format'
import { Building2, AlertTriangle, Search } from 'lucide-react'

export default function LendersPage() {
  const [lenders, setLenders] = useState<Lender[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'duplicate_attempts' | 'total_exposure' | 'total_invoices'>('duplicate_attempts')

  useEffect(() => {
    getLenders().then(r => setLenders(r.data)).catch(() => setLoadError(true)).finally(() => setLoading(false))
  }, [])

  const sorted = useMemo(() => lenders
    .filter((lender) => `${lender.lender_name} ${lender.lender_id} ${lender.lender_type}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => b[sortBy] - a[sortBy]), [lenders, search, sortBy])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-surface-700 pb-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Lender Intelligence</h2>
          <p className="mt-1 text-sm text-slate-500">Portfolio exposure and risk indicators by lender</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1 max-w-lg"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><input className="input w-full pl-9" aria-label="Search lenders" placeholder="Search lender name or ID" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        <label className="flex items-center gap-2 text-xs text-slate-600">Sort by<select className="input py-1.5" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}><option value="duplicate_attempts">Duplicate attempts</option><option value="total_exposure">Exposure</option><option value="total_invoices">Invoice count</option></select></label>
        {!loading && !loadError && <span className="text-xs text-slate-500">{sorted.length} lenders</span>}
      </div>

      {loadError && <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">Lender records could not be loaded. Check the API connection and retry.</div>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {loading && Array.from({ length: 6 }, (_, index) => <div key={index} className="h-52 animate-pulse rounded-md border border-surface-700 bg-white" />)}
        {sorted.map(l => (
          <article key={l.lender_id} className="card p-5 transition-all hover:border-blue-300 hover:shadow-md">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-md bg-surface-700 flex items-center justify-center">
                  <Building2 className="w-4 h-4 text-slate-400" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{l.lender_name}</div>
                  <div className="text-xs text-slate-500">{l.lender_type}</div>
                </div>
              </div>
              {l.duplicate_attempts > 0 && (
                  <div className="flex items-center gap-1 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] text-red-800">
                  <AlertTriangle className="w-3 h-3" />
                  {l.duplicate_attempts}
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="stat-label">Invoices</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{l.total_invoices.toLocaleString()}</div>
              </div>
              <div>
                <div className="stat-label">Exposure</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{formatCurrency(l.total_exposure)}</div>
              </div>
              <div>
                <div className="stat-label">High Risk</div>
                <div className={`text-lg font-bold mt-1 ${l.high_risk_count > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {l.high_risk_count.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="stat-label">Duplicate Attempts</div>
                <div className={`text-lg font-bold mt-1 ${l.duplicate_attempts > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                  {l.duplicate_attempts.toLocaleString()}
                </div>
              </div>
            </div>
          </article>
        ))}
        {!loading && !loadError && !sorted.length && <div className="card col-span-full p-8 text-center text-sm text-slate-500">No lenders match the current search.</div>}
      </div>
    </div>
  )
}
