import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ReactFlow,
  Background, Controls, MiniMap,
  type Node, type Edge,
  BackgroundVariant,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { motion } from 'framer-motion'
import { Search, Loader2, GitBranch, AlertTriangle, Info } from 'lucide-react'
import { getInvoiceGraph } from '@/services/api'
import type { GraphResponse, GraphNode as GNode } from '@/types'

const NODE_COLORS: Record<string, string> = {
  invoice: '#2563eb',
  company: '#476b87',
  lender: '#0891b2',
  eway: '#059669',
  financing: '#f59e0b',
}

const NODE_RISK_COLOR = '#dc2626'

function buildFlowNodes(graphData: GraphResponse): Node[] {
  return graphData.nodes.map((n: GNode) => {
    const isRisk = graphData.suspicious_node_ids.includes(n.id)
    const baseColor = isRisk ? NODE_RISK_COLOR : NODE_COLORS[n.type] ?? '#334155'

    return {
      id: n.id,
      type: 'default',
      position: { x: 0, y: 0 }, // will be set by layout
      data: {
        label: (
          <div className="text-center">
            <div style={{ color: '#17212f', fontSize: 11, fontWeight: 700 }}>{n.label}</div>
            <div style={{ color: '#64748b', fontSize: 9, marginTop: 2 }}>{n.type.toUpperCase()}</div>
            {n.properties['amount'] && (
              <div style={{ color: '#1d4ed8', fontSize: 9, marginTop: 1 }}>{n.properties['amount']}</div>
            )}
            {n.properties['role'] && (
              <div style={{ color: '#64748b', fontSize: 9 }}>{n.properties['role']}</div>
            )}
            {n.properties['status'] && (
              <div style={{ color: '#a16207', fontSize: 9 }}>{n.properties['status']}</div>
            )}
          </div>
        ),
      },
      style: {
        background: `${baseColor}22`,
        border: `1.5px solid ${baseColor}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 120,
        cursor: 'pointer',
      },
    }
  })
}

function buildFlowEdges(graphData: GraphResponse): Edge[] {
  return graphData.edges.map(e => {
    const isHighlighted = graphData.suspicious_edge_ids.includes(e.id)
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: isHighlighted,
      style: {
        stroke: isHighlighted ? '#dc2626' : '#334155',
        strokeWidth: isHighlighted ? 2 : 1,
      },
      labelStyle: { fill: '#64748b', fontSize: 9 },
      markerEnd: { type: MarkerType.ArrowClosed, color: isHighlighted ? '#dc2626' : '#334155' },
    }
  })
}

// Simple radial layout: invoice in center, others around it
function applyLayout(nodes: Node[]): Node[] {
  const centerNode = nodes.find(n => n.id.startsWith('inv_'))
  if (!centerNode) return nodes

  const others = nodes.filter(n => n.id !== centerNode.id)
  const radius = Math.max(200, others.length * 45)
  const angleStep = (2 * Math.PI) / Math.max(others.length, 1)

  const positioned: Node[] = [
    { ...centerNode, position: { x: 300, y: 300 } }
  ]

  others.forEach((n, i) => {
    const angle = i * angleStep - Math.PI / 2
    positioned.push({
      ...n,
      position: {
        x: 300 + radius * Math.cos(angle),
        y: 300 + radius * Math.sin(angle),
      },
    })
  })

  return positioned
}

export default function GraphPage() {
  const [searchParams] = useSearchParams()
  const [invoiceId, setInvoiceId] = useState(searchParams.get('id') ?? '')
  const [graph, setGraph] = useState<GraphResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [selectedNode, setSelectedNode] = useState<GNode | null>(null)

  const loadGraph = useCallback(async (id: string) => {
    if (!id.trim()) return
    setLoading(true)
    setError('')
    setSelectedNode(null)
    try {
      const res = await getInvoiceGraph(id.trim())
      const data = res.data
      setGraph(data)
      const flowNodes = buildFlowNodes(data)
      const positioned = applyLayout(flowNodes)
      setNodes(positioned)
      setEdges(buildFlowEdges(data))
    } catch {
      setGraph(null)
      setNodes([])
      setEdges([])
      setError('The graph could not be loaded for this invoice. Confirm the ID and try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const id = searchParams.get('id')
    if (id) {
      setInvoiceId(id)
      loadGraph(id)
    }
  }, [searchParams, loadGraph])

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    if (!graph) return
    const gNode = graph.nodes.find(n => n.id === node.id)
    if (gNode) setSelectedNode(gNode)
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Graph Intelligence</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Entity relationship visualization — seller, buyer, lender, and delivery proof networks
        </p>
      </div>

      {/* Search */}
      <div className="card">
        <div className="card-body">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                id="graph-invoice-input"
                className="input w-full pl-9 font-mono"
                aria-label="Invoice ID to visualize"
                placeholder="Enter an invoice ID"
                value={invoiceId}
                onChange={e => setInvoiceId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && loadGraph(invoiceId)}
              />
            </div>
            <button
              id="btn-load-graph"
              className="btn-primary"
              onClick={() => loadGraph(invoiceId)}
              disabled={loading || !invoiceId.trim()}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
              Load Graph
            </button>
          </div>
        </div>
      </div>

      {error && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      {/* Legend + risk warning */}
      {graph && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 text-xs text-slate-500">
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <span key={type} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm border" style={{ borderColor: color, background: `${color}22` }} />
                {type}
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm border border-red-500 bg-red-500/20" />
              high-risk
            </span>
          </div>
          {graph.suspicious_node_ids.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              {graph.suspicious_node_ids.length} suspicious nodes highlighted
            </div>
          )}
        </div>
      )}

      {/* Graph canvas */}
      <div className="flex flex-col gap-4 xl:flex-row">
        <motion.div
          className="card min-w-0 flex-1 overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{ height: 'min(68vh, 680px)', minHeight: 420 }}
        >
          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3 text-slate-500">
                <Loader2 className="w-6 h-6 animate-spin" />
                <span className="text-sm">Building investigation graph...</span>
              </div>
            </div>
          )}
          {!loading && !error && nodes.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <GitBranch className="mb-3 h-6 w-6 text-blue-800" />
              <div className="text-sm font-semibold text-slate-800">No graph selected</div>
              <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">Enter an invoice ID to visualize its entity network and connected financing relationships.</p>
            </div>
          )}
          {!loading && nodes.length > 0 && (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodeClick={handleNodeClick}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              attributionPosition="bottom-right"
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1a2540" />
              <Controls />
              <MiniMap nodeColor={n => {
                const gn = graph?.nodes.find(x => x.id === n.id)
                if (!gn) return '#334155'
                return graph?.suspicious_node_ids.includes(n.id) ? '#dc2626' : NODE_COLORS[gn.type] ?? '#334155'
              }} />
            </ReactFlow>
          )}
        </motion.div>

        {/* Node detail sidebar */}
        {selectedNode && (
          <motion.div
            className="card w-full flex-shrink-0 overflow-y-auto xl:w-64"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <div className="card-header">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-semibold text-slate-200">Node Details</span>
              </div>
            </div>
            <div className="card-body space-y-3">
              <div>
                <div className="stat-label">ID</div>
                <div className="font-mono text-xs text-blue-400 mt-1 break-all">{selectedNode.id}</div>
              </div>
              <div>
                <div className="stat-label">Label</div>
                <div className="text-sm text-slate-200 mt-1">{selectedNode.label}</div>
              </div>
              <div>
                <div className="stat-label">Type</div>
                <div className="text-sm mt-1">
                  <span className="badge-info">{selectedNode.type}</span>
                </div>
              </div>
              {selectedNode.risk_flag && (
                <div className="flex items-center gap-1.5 text-xs text-red-400 bg-red-950/20 border border-red-800/40 rounded px-2 py-1.5">
                  <AlertTriangle className="w-3 h-3" />
                  Suspicious Node
                </div>
              )}
              <div className="space-y-2 pt-2 border-t border-surface-700">
                {Object.entries(selectedNode.properties).map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[10px] text-slate-600 uppercase tracking-wider">{k}</div>
                    <div className="text-xs text-slate-300 font-mono mt-0.5 break-all">{v || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
