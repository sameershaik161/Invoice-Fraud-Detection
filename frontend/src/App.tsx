import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
const OverviewPage = lazy(() => import('@/pages/OverviewPage'))
const VerifyPage = lazy(() => import('@/pages/VerifyPage'))
const RiskMonitorPage = lazy(() => import('@/pages/RiskMonitorPage'))
const GraphPage = lazy(() => import('@/pages/GraphPage'))
const InvoicesPage = lazy(() => import('@/pages/InvoicesPage'))
const AddInvoicePage = lazy(() => import('@/pages/AddInvoicePage'))
const LendersPage = lazy(() => import('@/pages/LendersPage'))
const AuditPage = lazy(() => import('@/pages/AuditPage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const InvestigationPage = lazy(() => import('@/pages/InvestigationPage'))
const AlertsPage = lazy(() => import('@/pages/AlertsPage'))
const CopilotPage = lazy(() => import('@/pages/CopilotPage'))

function page(element: ReactNode) {
  return <Suspense fallback={<div className="py-10 text-center text-sm text-slate-500">Loading view…</div>}>{element}</Suspense>
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={page(<OverviewPage />)} />
        <Route path="/verify" element={page(<VerifyPage />)} />
        <Route path="/msme-verification" element={page(<VerifyPage />)} />
        <Route path="/msme" element={page(<VerifyPage />)} />
        <Route path="/risk" element={page(<RiskMonitorPage />)} />
        <Route path="/alerts" element={page(<AlertsPage />)} />
        <Route path="/copilot" element={page(<CopilotPage />)} />
        <Route path="/graph" element={page(<GraphPage />)} />
        <Route path="/invoices" element={page(<InvoicesPage />)} />
        <Route path="/invoices/add" element={page(<AddInvoicePage />)} />
        <Route path="/invoices/:id" element={page(<VerifyPage />)} />
        <Route path="/investigation/:invoiceId" element={page(<InvestigationPage />)} />
        <Route path="/lenders" element={page(<LendersPage />)} />
        <Route path="/audit" element={page(<AuditPage />)} />
        <Route path="/analytics" element={page(<AnalyticsPage />)} />
      </Route>
    </Routes>
  )
}
