import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, ShieldCheck, AlertTriangle, DollarSign, Building2,
  Search, Play, ArrowRight, Sparkles, Plus, GitBranch, ClipboardList
} from 'lucide-react'
import { getAnalytics, getDemoInvoice, getHealth, getInvoices, getOverview } from '@/services/api'
import type { Analytics, InvoiceListItem, Overview } from '@/types'
import { formatCurrency } from '@/utils/format'
import RiskBadge from '@/components/RiskBadge'

interface KPICard {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  tone: string
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState<Overview | null>(null)
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([])
  const [demoId, setDemoId] = useState('INV-2026-02970')
  const [searchId, setSearchId] = useState('')
  const [loadError, setLoadError] = useState(false)
  const [systemHealth, setSystemHealth] = useState({ api: 'checking', graph: 'unknown', data: 'unknown' })

  useEffect(() => {
    getOverview().then(r => setOverview(r.data)).catch(() => setLoadError(true))
    getAnalytics().then(r => setAnalytics(r.data)).catch(() => {})
    getInvoices({ limit: 500 }).then(r => setInvoices(r.data)).catch(() => {})
    getDemoInvoice().then(r => setDemoId(r.data.demo_invoice_id)).catch(() => {})
    getHealth().then(({ data }) => setSystemHealth({ api: 'connected', graph: data.neo4j_enabled ? 'connected' : 'degraded', data: data.data_loaded ? 'loaded' : 'unavailable' })).catch(() => setSystemHealth({ api: 'offline', graph: 'unknown', data: 'unknown' }))
  }, [])

  const cards: KPICard[] = overview
    ? [
        {
          label: 'Total Invoices',
          value: overview.total_invoices.toLocaleString(),
          icon: FileText, tone: 'text-blue-800 bg-blue-50',
        },
        {
          label: 'Verified Today',
          value: overview.verified_today?.toLocaleString() ?? 'Not available',
          sub: overview.verified_today === null ? 'No verification-event timestamps are stored' : 'in last 24h',
          icon: ShieldCheck, tone: 'text-green-800 bg-green-50',
        },
        {
          label: 'High-Risk Invoices',
          value: overview.high_risk_invoices.toLocaleString(),
          sub: `${overview.critical_invoices} critical`,
          icon: AlertTriangle, tone: 'text-red-800 bg-red-50',
        },
        {
          label: 'Exposure Flagged',
          value: formatCurrency(overview.potential_exposure),
          sub: 'on high-risk invoices',
          icon: DollarSign, tone: 'text-amber-800 bg-amber-50',
        },
        {
          label: 'Lenders Connected',
          value: overview.lenders_connected,
          icon: Building2, tone: 'text-cyan-800 bg-cyan-50',
        },
        {
          label: 'Duplicate Financing',
          value: overview.double_financing_count.toLocaleString(),
          sub: 'flagged records',
          icon: ClipboardList, tone: 'text-orange-800 bg-orange-50',
        },
      ]
    : []
  const healthIndicators: Array<{ label: string; value: string; good: boolean }> = [
    { label: 'API', value: systemHealth.api, good: systemHealth.api === 'connected' },
    { label: 'Graph', value: systemHealth.graph, good: systemHealth.graph === 'connected' },
    { label: 'Data', value: systemHealth.data, good: systemHealth.data === 'loaded' },
  ]

  return (
    <div className="space-y-6">
      <section className="dashboard-hero rounded-md px-5 py-6 text-white shadow-sm md:px-8 md:py-8">
        <div className="relative z-10 max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-100"><ShieldCheck className="h-3.5 w-3.5" /> Financial intelligence command center</div>
          <h2 className="text-2xl font-semibold leading-tight text-white md:text-3xl">Invoice Risk &amp; Fraud Intelligence</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-blue-100">Detect duplicate financing, uncover hidden relationships, and investigate invoice risk with evidence-led intelligence.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-semibold text-blue-900 transition hover:-translate-y-0.5 hover:bg-blue-50" onClick={() => navigate('/invoices/add')}><Plus className="h-4 w-4" /> Add Invoice</button>
            <button className="inline-flex items-center gap-2 rounded-md border border-white/35 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10" onClick={() => navigate(`/investigation/${demoId}`)}><ShieldCheck className="h-4 w-4" /> Open Investigation</button>
            <button className="inline-flex items-center gap-2 rounded-md border border-white/35 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10" onClick={() => navigate(`/copilot?invoiceId=${encodeURIComponent(demoId)}`)}><Sparkles className="h-4 w-4" /> Ask AI</button>
          </div>
        </div>
        <div className="relative z-10 mt-6 flex flex-wrap gap-x-5 gap-y-2 border-t border-white/15 pt-3 text-[11px] text-blue-100 md:mt-7">
          <span className="font-semibold uppercase tracking-wider text-white/75">System status</span>
          {healthIndicators.map(({ label, value, good }) => <span key={label} className="inline-flex items-center gap-1.5 capitalize"><span className={`h-1.5 w-1.5 rounded-full ${good ? 'bg-emerald-300' : value === 'unknown' || value === 'checking' ? 'bg-amber-300' : 'bg-red-300'}`} />{label}: {value}</span>)}
        </div>
      </section>

      {loadError && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">Unable to load portfolio metrics. Refresh the page to retry.</div>}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        {cards.length ? cards.map((card) => (
          <article key={card.label} className="kpi-card min-w-0 border border-surface-700 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <span className="stat-label leading-4">{card.label}</span>
              <span className={`rounded p-1.5 ${card.tone}`}><card.icon className="h-4 w-4" /></span>
            </div>
            <div className="mt-2 truncate text-xl font-semibold text-slate-900">{card.value}</div>
            {card.sub && <div className="mt-1 text-xs text-slate-500">{card.sub}</div>}
          </article>
        )) : Array.from({ length: 6 }, (_, index) => <div key={index} className="h-24 animate-pulse rounded-md border border-surface-700 bg-white" />)}
      </div>

      <section className="grid gap-5 xl:grid-cols-[0.85fr_1.6fr]">
        <div className="card overflow-hidden">
          <div className="card-header"><div><h3 className="text-base font-semibold text-slate-900">Risk Distribution</h3><p className="mt-1 text-xs text-slate-500">Counts reported by portfolio analytics</p></div></div>
          <div className="space-y-4 p-5">
            {analytics?.risk_distribution?.length ? analytics.risk_distribution.map((item) => {
              const total = analytics.risk_distribution.reduce((sum, risk) => sum + risk.count, 0)
              const width = total ? Math.round((item.count / total) * 100) : 0
              const color = item.level.toUpperCase() === 'CRITICAL' ? 'bg-red-600' : item.level.toUpperCase() === 'HIGH' ? 'bg-orange-500' : item.level.toUpperCase() === 'MEDIUM' ? 'bg-amber-500' : 'bg-green-600'
              return <div key={item.level}>
                <div className="mb-1 flex justify-between text-sm"><span className="text-slate-700">{item.level}</span><span className="font-mono text-slate-600">{item.count.toLocaleString()}</span></div>
                <div className="h-2 overflow-hidden rounded-sm bg-surface-700"><div className={`h-full ${color}`} style={{ width: `${width}%` }} /></div>
              </div>
            }) : <p className="text-sm text-slate-500">Risk distribution is not available.</p>}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="card-header"><div><h3 className="text-base font-semibold text-slate-900">High-Risk Invoices</h3><p className="mt-1 text-xs text-slate-500">Invoices flagged by the risk engine</p></div><button className="btn-ghost text-xs" onClick={() => navigate('/risk')}>Risk Monitor <ArrowRight className="h-3.5 w-3.5" /></button></div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[680px]"><thead><tr><th>Invoice ID</th><th>Seller</th><th>Buyer</th><th className="text-right">Amount</th><th>Risk</th><th>Action</th></tr></thead>
              <tbody>
                {invoices.filter((item) => item.risk_level === 'CRITICAL' || item.risk_level === 'HIGH').slice(0, 6).map((item) => <tr key={item.invoice_id} onClick={() => navigate(`/investigation/${item.invoice_id}`)}>
                  <td className="font-mono text-xs font-medium text-blue-800">{item.invoice_id}</td><td className="max-w-36 truncate">{item.seller_name}</td><td className="max-w-36 truncate">{item.buyer_name}</td><td className="text-right font-mono text-xs">{formatCurrency(item.net_amount)}</td><td><RiskBadge level={item.risk_level} size="sm" showIcon={false} /></td><td><button className="text-xs font-medium text-blue-800 hover:underline" onClick={(event) => { event.stopPropagation(); navigate(`/investigation/${item.invoice_id}`) }}>Investigate</button></td>
                </tr>)}
                {!invoices.length && <tr><td colSpan={6} className="py-8 text-center text-sm text-slate-500">Invoice risk records are unavailable.</td></tr>}
                {!!invoices.length && !invoices.some((item) => item.risk_level === 'CRITICAL' || item.risk_level === 'HIGH') && <tr><td colSpan={6} className="py-8 text-center text-sm text-slate-500">No high-risk invoices in the loaded results.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="card border-blue-200">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-blue-800" />
            <span className="text-sm font-semibold text-slate-900">Investigate an Invoice</span>
          </div>
          <button
            id="btn-load-demo"
            className="btn-ghost text-xs"
            onClick={() => setSearchId(demoId)}
          >
            Load Demo Invoice
          </button>
          <button
            className="btn-ghost text-xs"
            onClick={() => navigate(`/copilot?invoiceId=${encodeURIComponent(demoId)}`)}
          >
            <Sparkles className="h-3.5 w-3.5" /> Ask Copilot
          </button>
        </div>
        <div className="card-body">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="invoice-search-input"
                className="input w-full pl-9 font-mono"
                placeholder="Enter invoice ID (e.g. INV-2026-02970)"
                value={searchId}
                onChange={e => setSearchId(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && searchId.trim()) {
                    navigate(`/verify?id=${searchId.trim()}`)
                  }
                }}
              />
            </div>
            <button
              id="btn-verify-invoice"
              className="btn-primary"
              disabled={!searchId.trim()}
              onClick={() => navigate(`/verify?id=${searchId.trim()}`)}
            >
              <Play className="w-4 h-4" />
              Verify Invoice
            </button>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Demo scenario: {' '}
            <button
              className="text-blue-500 hover:text-blue-400 font-mono"
              onClick={() => setSearchId(demoId)}
            >
              {demoId}
            </button>{' '}
            for the full double-financing demo scenario.
          </p>
        </div>
      </section>

      {/* Quick links */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {[
          { label: 'Risk Monitor', desc: 'Review risk-engine findings', to: '/risk', icon: AlertTriangle },
          { label: 'Graph Intelligence', desc: 'Explore connected entities', to: `/graph?id=${encodeURIComponent(demoId)}`, icon: GitBranch },
          { label: 'Audit Trail', desc: 'Review recorded investigation events', to: '/audit', icon: ClipboardList },
        ].map(item => (
          <button
            key={item.label}
            className="card group flex items-center gap-3 p-4 text-left transition-colors hover:border-blue-300"
            onClick={() => navigate(item.to)}
          >
            <item.icon className="h-4 w-4 text-blue-800" />
            <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-slate-900">{item.label}</span><span className="mt-1 block text-xs text-slate-500">{item.desc}</span></span>
            <ArrowRight className="h-4 w-4 text-slate-500 transition-colors group-hover:text-blue-800" />
          </button>
        ))}
      </div>
    </div>
  )
}
