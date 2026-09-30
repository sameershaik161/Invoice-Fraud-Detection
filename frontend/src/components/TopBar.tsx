import { Activity, AlertCircle, Bell, Menu, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react'
import { useState, useEffect } from 'react'
import { getHealth } from '@/services/api'
import GlobalSearch from '@/components/GlobalSearch'
import { Link } from 'react-router-dom'

interface SystemHealth {
  api: 'ok' | 'error' | 'loading'
  graph: 'connected' | 'degraded' | 'unknown'
  data: 'loaded' | 'unavailable' | 'unknown'
}

export default function TopBar({ onMenuClick, onSidebarToggle, sidebarCollapsed }: { onMenuClick: () => void; onSidebarToggle: () => void; sidebarCollapsed: boolean }) {
  const [status, setStatus] = useState<SystemHealth>({ api: 'loading', graph: 'unknown', data: 'unknown' })

  useEffect(() => {
    getHealth()
      .then(({ data }) => setStatus({ api: 'ok', graph: data.neo4j_enabled ? 'connected' : 'degraded', data: data.data_loaded ? 'loaded' : 'unavailable' }))
      .catch(() => setStatus({ api: 'error', graph: 'unknown', data: 'unknown' }))
  }, [])

  return (
    <header className="flex min-h-16 flex-shrink-0 items-center justify-between gap-3 border-b border-surface-700 bg-white px-3 md:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button className="btn-ghost hidden border-0 px-2 md:inline-flex" onClick={onSidebarToggle} aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'} title={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}>{sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}</button>
        <button className="btn-ghost border-0 px-2 md:hidden" onClick={onMenuClick} aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
        <div className="hidden shrink-0 lg:block">
          <h1 className="text-sm font-semibold text-slate-900">InvoiceFactoringGuard</h1>
          <span className="text-[11px] text-slate-500">Invoice Risk &amp; Fraud Intelligence</span>
        </div>
        <div className="min-w-0 flex-1 max-w-2xl lg:ml-3">
          <GlobalSearch />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:gap-4">
        <div className="hidden items-center gap-3 text-[10px] lg:flex" aria-label="System status">
          <span className={`flex items-center gap-1 ${status.api === 'ok' ? 'text-green-700' : status.api === 'error' ? 'text-red-700' : 'text-slate-500'}`}>
            {status.api === 'loading' ? <Activity className="h-3 w-3 animate-pulse" /> : status.api === 'error' ? <AlertCircle className="h-3 w-3" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
            API {status.api === 'ok' ? 'Connected' : status.api === 'error' ? 'Offline' : 'Checking'}
          </span>
          <span className={`flex items-center gap-1 ${status.graph === 'connected' ? 'text-green-700' : status.graph === 'degraded' ? 'text-amber-700' : 'text-slate-500'}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />Graph {status.graph === 'connected' ? 'Connected' : status.graph === 'degraded' ? 'Degraded' : 'Unknown'}</span>
          <span className={`flex items-center gap-1 ${status.data === 'loaded' ? 'text-green-700' : status.data === 'unavailable' ? 'text-amber-700' : 'text-slate-500'}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />Data {status.data === 'loaded' ? 'Loaded' : status.data === 'unavailable' ? 'Unavailable' : 'Unknown'}</span>
        </div>
        <Link to="/copilot" className="btn-ghost px-2 md:px-3" aria-label="Open AI Copilot" title="AI Copilot"><Sparkles className="h-4 w-4" /><span className="hidden md:inline">Copilot</span></Link>
        <Link to="/alerts" className="btn-ghost px-2" aria-label="Open alerts" title="Alert Center"><Bell className="h-4 w-4" /></Link>
      </div>
    </header>
  )
}
