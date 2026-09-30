import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import { Outlet, useLocation } from 'react-router-dom'
import { useState } from 'react'

export default function AppLayout() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const pageName = location.pathname === '/' ? 'Dashboard'
    : location.pathname.startsWith('/invoices/add') ? 'Add Invoice'
      : location.pathname.startsWith('/invoices') ? 'Invoices'
        : location.pathname.startsWith('/investigation') ? 'Investigation Workspace'
          : location.pathname.startsWith('/graph') ? 'Graph Intelligence'
            : location.pathname.startsWith('/copilot') ? 'AI Copilot'
              : location.pathname.startsWith('/risk') ? 'Risk Monitor'
                : location.pathname.startsWith('/alerts') ? 'Alert Center'
                  : location.pathname.startsWith('/audit') ? 'Audit Trail'
                    : location.pathname.startsWith('/analytics') ? 'Analytics'
                      : location.pathname.startsWith('/lenders') ? 'Lenders'
                        : 'MSME Verification'

  return (
    <div className="app-shell flex h-screen overflow-hidden">
      {sidebarOpen && <button className="fixed inset-0 z-30 bg-slate-900/30 md:hidden" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <Sidebar open={sidebarOpen} collapsed={sidebarCollapsed} onNavigate={() => setSidebarOpen(false)} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar
          onMenuClick={() => setSidebarOpen((open) => !open)}
          onSidebarToggle={() => setSidebarCollapsed((collapsed) => !collapsed)}
          sidebarCollapsed={sidebarCollapsed}
        />
        <main className="flex-1 overflow-y-auto bg-surface-950 p-4 md:p-6">
          <nav aria-label="Breadcrumb" className="mb-4 text-xs text-slate-500">
            <span>InvoiceFactoringGuard</span><span className="mx-2 text-slate-400">/</span><span aria-current="page" className="font-medium text-slate-700">{pageName}</span>
          </nav>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
