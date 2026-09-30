import { useEffect, useState } from 'react'
import { getAnalytics } from '@/services/api'
import type { Analytics } from '@/types'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line, Legend,
} from 'recharts'

const RISK_COLORS: Record<string, string> = {
  LOW: '#15803d',
  MEDIUM: '#a16207',
  HIGH: '#c2410c',
  CRITICAL: '#b91c1c',
}

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean; payload?: Array<{ name: string; value: number; color?: string }>; label?: string
}) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-surface-600 bg-white px-3 py-2 text-xs shadow-md">
      <div className="mb-1 text-slate-600">{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color ?? '#94a3b8' }}>{p.name}: {p.value}</div>
      ))}
    </div>
  )
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    getAnalytics().then(r => setData(r.data)).catch(() => setLoadError(true)).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="space-y-4"><div className="h-8 w-48 animate-pulse rounded bg-surface-700" /><div className="grid gap-4 md:grid-cols-2"><div className="h-72 animate-pulse rounded-md border border-surface-700 bg-white" /><div className="h-72 animate-pulse rounded-md border border-surface-700 bg-white" /><div className="h-72 animate-pulse rounded-md border border-surface-700 bg-white" /><div className="h-72 animate-pulse rounded-md border border-surface-700 bg-white" /></div></div>
    )
  }

  if (!data) return <div role="alert" className="card p-5"><div className="text-sm font-semibold text-red-800">Analytics unavailable</div><p className="mt-1 text-sm text-slate-600">{loadError ? 'Analytics data could not be loaded from the API.' : 'No analytics data was returned.'}</p><button className="btn-ghost mt-3" onClick={() => { setLoading(true); setLoadError(false); getAnalytics().then((response) => setData(response.data)).catch(() => setLoadError(true)).finally(() => setLoading(false)) }}>Retry</button></div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Portfolio Analytics</h2>
        <p className="mt-1 text-sm text-slate-500">Risk distribution, lender exposure, and historical financing patterns</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Risk Distribution Pie */}
        <div className="card">
          <div className="card-header"><span className="text-sm font-semibold text-slate-900">Risk Distribution</span></div>
          <div className="card-body flex items-center justify-center" style={{ height: 280 }}>
            {!data.risk_distribution.length ? <p className="text-sm text-slate-500">Risk distribution is not available.</p> :
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.risk_distribution}
                  dataKey="count"
                  nameKey="level"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  label={({ level, count }) => `${level} ${count}`}
                  labelLine={{ stroke: '#94a3b8' }}
                >
                  {data.risk_distribution.map(entry => (
                    <Cell key={entry.level} fill={RISK_COLORS[entry.level] ?? '#334155'} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>}
          </div>
        </div>

        {/* Amount by Risk Level */}
        <div className="card">
          <div className="card-header"><span className="text-sm font-semibold text-slate-900">Exposure by Risk Level (₹ Cr)</span></div>
          <div className="card-body" style={{ height: 260 }}>
            {!data.amount_by_risk.length ? <div className="flex h-full items-center justify-center text-sm text-slate-500">Exposure by risk is not available.</div> :
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.amount_by_risk} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ef" />
                <XAxis dataKey="level" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="amount_cr" name="₹ Cr" radius={[4, 4, 0, 0]}>
                  {data.amount_by_risk.map(entry => (
                    <Cell key={entry.level} fill={RISK_COLORS[entry.level] ?? '#3b82f6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>}
          </div>
        </div>

        {/* Financing by Lender */}
        <div className="card">
          <div className="card-header"><span className="text-sm font-semibold text-slate-900">Financing by Lender (₹ Lakh)</span></div>
          <div className="card-body" style={{ height: 260 }}>
            {!data.financing_by_lender.length ? <div className="flex h-full items-center justify-center text-sm text-slate-500">Lender financing data is not available.</div> :
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.financing_by_lender.slice(0, 10)}
                layout="vertical"
                margin={{ top: 0, right: 16, left: 60, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ef" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis type="category" dataKey="lender" tick={{ fontSize: 9, fill: '#64748b' }} width={55} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="amount" name="₹ L" fill="#1e40af" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>}
          </div>
        </div>

        {/* Monthly Duplicates */}
        <div className="card">
          <div className="card-header"><span className="text-sm font-semibold text-slate-900">Duplicate Financing Attempts by Month</span></div>
          <div className="card-body" style={{ height: 260 }}>
            {!data.monthly_duplicates.length ? <div className="flex h-full items-center justify-center text-sm text-slate-500">Monthly duplicate data is not available.</div> :
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.monthly_duplicates}
                margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ef" />
                <XAxis dataKey="month" tick={{ fontSize: 9, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 10, color: '#64748b' }} />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Duplicates"
                  stroke="#b91c1c"
                  strokeWidth={2}
                  dot={{ fill: '#b91c1c', r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>}
          </div>
        </div>

        {/* Industry Risk */}
        <div className="card xl:col-span-2">
          <div className="card-header">
            <span className="text-sm font-semibold text-slate-900">Average Risk Score by Industry</span>
          </div>
          <div className="card-body" style={{ height: 220 }}>
            {!data.industry_risk.length ? <div className="flex h-full items-center justify-center text-sm text-slate-500">Industry risk data is not available.</div> :
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.industry_risk} margin={{ top: 0, right: 16, left: 0, bottom: 32 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ef" />
                <XAxis dataKey="industry" tick={{ fontSize: 9, fill: '#64748b' }} angle={-25} textAnchor="end" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="avg_risk" name="Avg Risk" fill="#315f91" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>}
          </div>
        </div>
      </div>
    </div>
  )
}
