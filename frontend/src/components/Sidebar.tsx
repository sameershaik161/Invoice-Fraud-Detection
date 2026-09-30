import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Building2,
  ScrollText,
  BarChart3,
  Zap,
  Sparkles,
  Plus,
  Network,
  ClipboardCheck,
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/invoices/add', label: 'Add Invoice', icon: Plus },
  { to: '/investigation/INV-2026-02970', label: 'Investigation Workspace', icon: ShieldCheck },
  { to: '/risk', label: 'Risk Monitor', icon: AlertTriangle },
  { to: '/graph', label: 'Graph Intelligence', icon: Network },
  { to: '/alerts', label: 'Alert Center', icon: AlertTriangle },
  { to: '/copilot', label: 'AI Copilot', icon: Sparkles },
  { to: '/msme-verification', label: 'MSME Verification', icon: ClipboardCheck },
  { to: '/lenders', label: 'Lenders', icon: Building2 },
  { to: '/audit', label: 'Audit Trail', icon: ScrollText },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
]

export default function Sidebar({ open, collapsed, onNavigate }: { open: boolean; collapsed: boolean; onNavigate: () => void }) {
  const location = useLocation()

  return (
    <aside className={`app-sidebar fixed inset-y-0 left-0 z-40 w-64 flex-shrink-0 flex-col border-r border-surface-700 bg-white shadow-lg transition-all duration-200 md:static md:z-auto md:flex md:shadow-none ${open ? 'flex' : 'hidden'} ${collapsed ? 'md:w-[60px]' : 'md:w-60'}`}>
      {/* Logo */}
      <div className={`border-b border-surface-700 py-5 ${collapsed ? 'px-2' : 'px-4'}`}>
        <div className={`mb-1 flex items-center gap-2 ${collapsed ? 'md:justify-center' : ''}`}>
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-800">
            <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <span className={`font-bold text-slate-900 text-sm leading-tight ${collapsed ? 'md:hidden' : ''}`}>InvoiceFactoringGuard</span>
        </div>
        <p className={`text-[11px] text-slate-500 leading-tight ml-10 ${collapsed ? 'md:hidden' : ''}`}>
          Invoice Risk &amp; Fraud Intelligence
        </p>
      </div>

      {/* Nav */}
      <nav className={`flex-1 space-y-0.5 overflow-y-auto p-3 ${collapsed ? 'md:px-2' : ''}`}>
        {navItems.map(({ to, label, icon: Icon }) => {
          const isActive =
            to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
          return (
            <NavLink
              key={to}
              to={to}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              aria-label={label}
              className={clsx('nav-link', isActive && 'active', collapsed && 'md:justify-center md:px-2')}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className={collapsed ? 'md:hidden' : ''}>{label}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className={`border-t border-surface-700 px-4 py-3 ${collapsed ? 'md:hidden' : ''}`}>
        <p className="text-[10px] text-slate-600 leading-snug">
          Synthetic demo data only.
          <br />
          Not real banking records.
        </p>
      </div>
    </aside>
  )
}
