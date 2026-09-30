import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ShieldAlert, Clock3 } from 'lucide-react'
import { getAlerts } from '@/services/api'
import type { AlertItem } from '@/types'
import RiskBadge from '@/components/RiskBadge'

const filters = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const

export default function AlertsPage() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [filter, setFilter] = useState<(typeof filters)[number]>('ALL')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    getAlerts().then((res) => setAlerts(res.data)).catch(() => { setAlerts([]); setLoadError(true) }).finally(() => setLoading(false))
  }, [])

  const visibleAlerts = useMemo(() => {
    if (filter === 'ALL') return alerts
    return alerts.filter((item) => item.level === filter)
  }, [alerts, filter])

  return (
    <div className="space-y-4">
      <div className="border-b border-surface-700 pb-4">
        <h2 className="text-2xl font-semibold text-slate-900">Alert Center</h2>
        <p className="mt-1 text-sm text-slate-500">Risk alerts generated from verified risk-engine results</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <span className="text-sm font-semibold text-slate-900">Filter by severity</span>
          </div>
          <div className="flex items-center gap-2">
            {filters.map((level) => (
              <button
                key={level}
                className={`rounded px-2.5 py-1 text-xs font-semibold transition-colors ${filter === level ? 'bg-blue-800 text-white' : 'bg-surface-800 text-slate-600 hover:bg-blue-50 hover:text-blue-800'}`}
                onClick={() => setFilter(level)}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
        <div className="card-body space-y-3">
          {loading ? Array.from({ length: 3 }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-md border border-surface-700 bg-surface-800" />) : loadError ? (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">Alert records could not be loaded. Check the API connection and retry.</div>
          ) : visibleAlerts.length === 0 ? (
            <div className="rounded-md border border-surface-700 bg-surface-800 px-4 py-8 text-center text-sm text-slate-600">No alerts match the selected severity.</div>
          ) : (
            visibleAlerts.map((alert) => (
              <div key={`${alert.invoice_id}-${alert.level}`} className="rounded-md border border-surface-700 bg-white p-4 transition-colors hover:border-surface-600">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className={alert.level === 'CRITICAL' ? 'w-4 h-4 text-red-400' : alert.level === 'HIGH' ? 'w-4 h-4 text-orange-400' : alert.level === 'MEDIUM' ? 'w-4 h-4 text-amber-400' : 'w-4 h-4 text-green-400'} />
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{alert.level}</div>
                      <div className="mt-1 text-base font-semibold text-slate-100">{alert.invoice_id}</div>
                    </div>
                  </div>
                  <RiskBadge level={alert.level as any} showIcon={false} size="sm" />
                </div>
                <div className="mt-3 text-sm text-slate-300">{alert.title}</div>
                <div className="mt-2 text-xs text-slate-500">{alert.message}</div>
                <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-slate-500">
                  <span className="flex items-center gap-1"><Clock3 className="w-3.5 h-3.5" /> {alert.timestamp}</span>
                  <button className="btn-ghost text-xs" onClick={() => navigate(alert.route)}>View Investigation</button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
