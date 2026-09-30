import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  BackgroundVariant,
  type Node,
  type Edge,
} from '@xyflow/react'
import {
  AlertTriangle,
  Download,
  FileText,
  ShieldCheck,
  GitBranch,
  ArrowRight,
  Sparkles,
} from 'lucide-react'
import { getInvestigation, getDemoInvoice } from '@/services/api'
import type { InvestigationData, GraphResponse, GraphNode } from '@/types'
import RiskEvidencePanel from '@/components/RiskEvidencePanel'
import FinancingTimeline from '@/components/FinancingTimeline'
import { formatCurrency } from '@/utils/format'

const NODE_COLORS: Record<string, string> = {
  invoice: '#2563eb',
  company: '#476b87',
  lender: '#0891b2',
  eway: '#059669',
  financing: '#f59e0b',
}

function buildFlowNodes(graph: GraphResponse): Node[] {
  return graph.nodes.map((node) => ({
    id: node.id,
    type: 'default',
    position: { x: 0, y: 0 },
    data: {
      label: (
        <div className="text-center">
          <div style={{ color: '#17212f', fontSize: 11, fontWeight: 700 }}>{node.label}</div>
          <div style={{ color: '#64748b', fontSize: 9 }}>{node.type.toUpperCase()}</div>
        </div>
      ),
    },
    style: {
      background: `${graph.suspicious_node_ids.includes(node.id) ? '#dc2626' : NODE_COLORS[node.type] ?? '#334155'}22`,
      border: `1.5px solid ${graph.suspicious_node_ids.includes(node.id) ? '#dc2626' : NODE_COLORS[node.type] ?? '#334155'}`,
      borderRadius: 8,
      padding: '8px 12px',
      minWidth: 120,
      cursor: 'pointer',
    },
  }))
}

function buildFlowEdges(graph: GraphResponse): Edge[] {
  return graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    animated: edge.highlighted,
    style: {
      stroke: edge.highlighted ? '#dc2626' : '#334155',
      strokeWidth: edge.highlighted ? 2 : 1,
    },
    labelStyle: { fill: '#64748b', fontSize: 9 },
    markerEnd: { type: MarkerType.ArrowClosed, color: edge.highlighted ? '#dc2626' : '#334155' },
  }))
}

function applyLayout(nodes: Node[]): Node[] {
  const center = nodes.find((node) => node.id.startsWith('inv_')) ?? nodes[0]
  if (!center) return nodes

  const others = nodes.filter((node) => node.id !== center.id)
  const radius = Math.max(200, others.length * 55)
  const angleStep = (2 * Math.PI) / Math.max(others.length, 1)

  return [
    { ...center, position: { x: 320, y: 220 } },
    ...others.map((node, index) => ({
      ...node,
      position: {
        x: 320 + radius * Math.cos(index * angleStep - Math.PI / 2),
        y: 220 + radius * Math.sin(index * angleStep - Math.PI / 2),
      },
    })),
  ]
}

export default function InvestigationPage() {
  const { invoiceId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<InvestigationData | null>(null)
  const [loading, setLoading] = useState(true)
  const [demoId, setDemoId] = useState('INV-2026-02970')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  useEffect(() => {
    getDemoInvoice().then((res) => setDemoId(res.data.demo_invoice_id)).catch(() => {})
  }, [])

  useEffect(() => {
    const id = invoiceId || demoId
    if (!id) return
    setLoading(true)
    getInvestigation(id)
      .then((res) => {
        setData(res.data)
        setSelectedNode(res.data.graph.nodes.find((node: GraphNode) => node.id.startsWith('inv_')) ?? null)
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [invoiceId, demoId])

  const handleDownloadReport = () => {
    if (!data) return
    const content = [
      'INVOICEFACTORINGGUARD',
      '',
      `Invoice ID: ${data.invoice_id}`,
      `Seller: ${data.invoice.seller_name}`,
      `Buyer: ${data.invoice.buyer_name}`,
      `Invoice Amount: ${formatCurrency(data.invoice.net_amount)}`,
      `Risk Score: ${data.risk.risk_score}/100`,
      `Risk Classification: ${data.risk.risk_level}`,
      `Recommended Action: ${data.risk.recommended_action}`,
      '',
      'Risk Evidence:',
      ...data.evidence.map((item) => `- ${item.title}: ${item.detail}`),
      '',
      'Timeline:',
      ...data.timeline.map((item) => `- ${item.date}: ${item.label} — ${item.detail}`),
      '',
      `Audit Summary: ${data.risk.summary}`,
    ].join('\n')

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.invoice_id}-investigation-report.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <div className="card"><div className="card-body text-sm text-slate-500">Loading investigation workspace…</div></div>
  }

  if (!data) {
    return <div className="card"><div className="card-body text-sm text-red-400">Unable to load investigation data for this invoice.</div></div>
  }

  const graphNodes = applyLayout(buildFlowNodes(data.graph))
  const graphEdges = buildFlowEdges(data.graph)
  const riskColor = data.risk.risk_level === 'CRITICAL' ? 'text-red-300' : data.risk.risk_level === 'HIGH' ? 'text-orange-300' : 'text-amber-300'

  return (
    <div className="space-y-5">
      <div className="card border-blue-800/40">
        <div className="card-header">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-blue-400">Invoice Investigation</div>
            <div className="mt-1 text-2xl font-bold text-slate-50">{data.invoice_id}</div>
          </div>
          <div className="flex items-center gap-2">
            <span className={data.risk.risk_level === 'CRITICAL' ? 'badge-critical' : data.risk.risk_level === 'HIGH' ? 'badge-high' : data.risk.risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low'}>{data.risk.risk_level}</span>
            <span className="badge-info">{data.risk.risk_score}/100</span>
          </div>
        </div>
        <div className="card-body grid gap-4 md:grid-cols-4">
          <div>
            <div className="stat-label">Risk</div>
            <div className={`mt-1 text-lg font-semibold ${riskColor}`}>{data.risk.risk_level}</div>
          </div>
          <div>
            <div className="stat-label">Score</div>
            <div className="mt-1 text-lg font-semibold text-slate-100">{data.risk.risk_score} / 100</div>
          </div>
          <div>
            <div className="stat-label">Status</div>
            <div className="mt-1 text-lg font-semibold text-amber-300">REVIEW REQUIRED</div>
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <button className="btn-primary" onClick={() => navigate('/risk')}><ShieldCheck className="w-4 h-4" /> Hold Payout</button>
            <button className="btn-ghost" onClick={() => navigate(`/verify?id=${data.invoice_id}`)}><AlertTriangle className="w-4 h-4" /> Request Verification</button>
            <button className="btn-ghost" onClick={() => navigate(`/copilot?invoiceId=${encodeURIComponent(data.invoice_id)}`)}><Sparkles className="w-4 h-4" /> Ask Copilot</button>
            <button className="btn-ghost" onClick={handleDownloadReport}><Download className="w-4 h-4" /> Generate Report</button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <div className="card overflow-hidden">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-semibold text-slate-200">Neo4j Investigation Graph</span>
            </div>
            <button className="btn-ghost text-xs" onClick={() => navigate(`/graph?id=${data.invoice_id}`)}>Open full graph</button>
          </div>
          <div style={{ height: 420 }}>
            <ReactFlow
              nodes={graphNodes}
              edges={graphEdges}
              fitView
              fitViewOptions={{ padding: 0.35 }}
              onNodeClick={(_, node) => {
                const item = data.graph.nodes.find((graphNode) => graphNode.id === node.id)
                if (item) setSelectedNode(item)
              }}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1a2540" />
              <Controls />
              <MiniMap nodeColor={(n) => {
                const match = data.graph.nodes.find((item) => item.id === n.id)
                if (!match) return '#334155'
                return data.graph.suspicious_node_ids.includes(match.id) ? '#dc2626' : NODE_COLORS[match.type] ?? '#334155'
              }} />
            </ReactFlow>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-sm font-semibold text-slate-200">Why is this invoice risky?</span>
            </div>
          </div>
          <div className="card-body">
            <RiskEvidencePanel evidence={data.evidence.map((item) => ({
              step: item.step,
              title: item.title,
              detail: item.detail,
              severity: item.severity,
            }))} />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-semibold text-slate-200">Financing Timeline</span>
          </div>
        </div>
        <div className="card-body">
          <FinancingTimeline events={data.timeline.map((event) => ({
            date: event.date || 'Date unavailable',
            label: event.label,
            detail: event.detail,
            severity: event.severity,
          }))} />
        </div>
      </div>

      {selectedNode && (
        <div className="card">
          <div className="card-header">
            <span className="text-sm font-semibold text-slate-200">Entity Details</span>
          </div>
          <div className="card-body grid gap-3 md:grid-cols-3">
            <div>
              <div className="stat-label">Entity Type</div>
              <div className="mt-1 text-base font-semibold text-slate-100">{selectedNode.type.toUpperCase()}</div>
            </div>
            <div>
              <div className="stat-label">Label</div>
              <div className="mt-1 text-base font-semibold text-slate-100">{selectedNode.label}</div>
            </div>
            <div>
              <div className="stat-label">Identifier</div>
              <div className="mt-1 text-base font-mono text-blue-400 break-all">{selectedNode.id}</div>
            </div>
            {Object.entries(selectedNode.properties).map(([key, value]) => (
              <div key={key}>
                <div className="stat-label">{key}</div>
                <div className="mt-1 text-sm text-slate-300 break-all">{String(value || '—')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <ArrowRight className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-semibold text-slate-200">Recommended Action</span>
          </div>
        </div>
        <div className="card-body flex items-center justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-slate-100">{data.risk.recommended_action}</div>
            <div className="text-sm text-slate-500">{data.risk.summary}</div>
          </div>
          <button className="btn-primary" onClick={() => navigate(`/verify?id=${data.invoice_id}`)}>Open Verification</button>
        </div>
      </div>
    </div>
  )
}
