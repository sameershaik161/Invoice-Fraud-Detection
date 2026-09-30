import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Bot, Check, Clipboard, Download, Loader2, MessageSquareText, RotateCcw, Send, Shield, Sparkles, Trash2 } from 'lucide-react'
import { getCopilotStatus, getGlobalSearch, postCopilotChat } from '@/services/api'
import type { CopilotResponse, CopilotStatus } from '@/types'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  result?: CopilotResponse
}

const suggestions = [
  'Why is this invoice risky?',
  'Who financed it?',
  'Is there duplicate financing?',
  'Show the company network.',
  'Show delivery evidence.',
  'Check GSTIN activity.',
  'Find matching line items.',
  'Generate an investigation summary.',
]

type ContextEntityType = 'invoice' | 'company' | 'lender' | 'gstin'

const contextPatterns: Record<ContextEntityType, RegExp> = {
  invoice: /^INV[-/ ]?\d{4}[-/ ]?\d{3,8}$/i,
  company: /^CMP\d{3,8}$/i,
  lender: /^LND\d{3,6}$/i,
  gstin: /^\d{2}[A-Z0-9]{13}$/i,
}

async function resolveContextIdentifier(type: ContextEntityType, rawValue: string): Promise<string> {
  const value = rawValue.trim()
  if (contextPatterns[type].test(value)) return value

  if (type === 'company' || type === 'lender') {
    const response = await getGlobalSearch(value)
    const expectedType = type === 'company' ? 'COMPANIES' : 'LENDERS'
    const matches = response.data.results.filter((item) => item.type === expectedType)
    const exactMatches = matches.filter((item) => item.label.toLowerCase() === value.toLowerCase())
    const candidates = exactMatches.length ? exactMatches : matches
    if (candidates.length === 1) return candidates[0].id
    if (candidates.length > 1) throw new Error(`More than one ${type} matched. Enter its project ID, such as ${type === 'company' ? 'CMP0836' : 'LND013'}.`)
  }

  throw new Error(`Enter a valid ${type} identifier${type === 'company' ? ' (for example, CMP0836)' : type === 'lender' ? ' (for example, LND013)' : type === 'invoice' ? ' (for example, INV-2026-02970)' : ' (15-character GSTIN)'}.`)
}

export default function CopilotPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [contextEntityId, setContextEntityId] = useState(searchParams.get('entityId') ?? searchParams.get('invoiceId') ?? '')
  const [contextEntityType, setContextEntityType] = useState<ContextEntityType>(searchParams.get('entityType') as ContextEntityType ?? 'invoice')
  const [providerStatus, setProviderStatus] = useState<CopilotStatus>({ configured: false, provider: 'none', fallback_providers: [], mode: 'Evidence Mode' })
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [generatedReport, setGeneratedReport] = useState<{ name: string; content: string; invoiceId: string } | null>(null)
  const lastQuestion = [...messages].reverse().find((message) => message.role === 'user')?.content

  useEffect(() => {
    getCopilotStatus().then((response) => setProviderStatus(response.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const entityId = searchParams.get('entityId') ?? searchParams.get('invoiceId') ?? ''
    const requestedType = searchParams.get('entityType')
    const entityType = ['invoice', 'company', 'lender', 'gstin'].includes(requestedType ?? '')
      ? requestedType as 'invoice' | 'company' | 'lender' | 'gstin'
      : 'invoice'
    setContextEntityId(entityId)
    setContextEntityType(entityType)
  }, [searchParams])

  const sendQuestion = async (
    question = draft,
    historyOverride?: Array<{ role: 'user' | 'assistant'; content: string }>,
    appendUser = true,
  ) => {
    const content = question.trim()
    if (!content || loading) return
    const userMessage: ChatMessage = { id: Date.now(), role: 'user', content }
    const priorHistory = historyOverride ?? messages.slice(-10).map(({ role, content: text }) => ({ role, content: text }))
    if (appendUser) setMessages((current) => [...current, userMessage])
    setDraft('')
    setError('')
    setLoading(true)
    try {
      const resolvedContextId = contextEntityId.trim()
        ? await resolveContextIdentifier(contextEntityType, contextEntityId)
        : ''
      if (resolvedContextId && resolvedContextId !== contextEntityId.trim()) {
        setContextEntityId(resolvedContextId)
        setSearchParams(contextEntityType === 'invoice'
          ? { invoiceId: resolvedContextId }
          : { entityId: resolvedContextId, entityType: contextEntityType }, { replace: true })
      }
      const response = await postCopilotChat({
        message: content,
        invoice_id: contextEntityType === 'invoice' ? resolvedContextId || undefined : undefined,
        context_entity_id: resolvedContextId || undefined,
        context_entity_type: resolvedContextId ? contextEntityType : undefined,
        history: priorHistory,
      })
      const result = response.data
      if (result.invoice_id && !contextEntityId) {
        setContextEntityId(result.invoice_id)
        setContextEntityType('invoice')
        setSearchParams({ invoiceId: result.invoice_id }, { replace: true })
      }
      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: 'assistant',
        content: result.answer,
        result,
      }])
    } catch (requestError) {
      const detail = (requestError as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      const message = typeof detail === 'string'
        ? detail
        : requestError instanceof Error ? requestError.message : 'The Copilot request failed.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const clearConversation = () => {
    setMessages([])
    setError('')
    setCopiedId(null)
  }

  const copyAnswer = async (message: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopiedId(message.id)
      window.setTimeout(() => setCopiedId(null), 1400)
    } catch {
      setError('Clipboard access is unavailable in this browser.')
    }
  }

  const downloadReport = (message: ChatMessage) => {
    const report = message.result?.report_text
    const invoice = message.result?.invoice_id
    if (!report || !invoice) return
    const name = `${message.result?.invoice_id ?? 'investigation'}-copilot-report.txt`
    setGeneratedReport({ name, content: report, invoiceId: invoice })
    saveReport(invoice)
  }

  const saveReport = (invoiceId: string) => {
    const anchor = document.createElement('a')
    anchor.href = `/api/copilot/report?invoice_id=${encodeURIComponent(invoiceId)}`
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  }

  const regenerate = () => {
    if (!lastQuestion || loading) return
    const lastUserIndex = messages.lastIndexOf([...messages].reverse().find((message) => message.role === 'user')!)
    const history = messages.slice(0, lastUserIndex).map(({ role, content }) => ({ role, content }))
    setMessages((current) => current.slice(0, lastUserIndex + 1))
    void sendQuestion(lastQuestion, history, false)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-7rem)] max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-blue-300">
            <Sparkles className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">AI Provider: {providerStatus.configured ? `Configured (${providerStatus.provider})` : 'Evidence Mode'}</span>
          </div>
          <h2 className="mt-1 text-xl font-semibold text-slate-100">AI Investigation Copilot</h2>
        </div>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="copilot-entity-type">Current entity type</label>
          <select
            id="copilot-entity-type"
            className="input w-28 text-xs"
            value={contextEntityType}
            onChange={(event) => {
              const type = event.target.value as 'invoice' | 'company' | 'lender' | 'gstin'
              setContextEntityType(type)
              if (contextEntityId.trim()) setSearchParams(type === 'invoice' ? { invoiceId: contextEntityId.trim() } : { entityId: contextEntityId.trim(), entityType: type }, { replace: true })
            }}
          >
            <option value="invoice">Invoice</option><option value="company">Company</option><option value="lender">Lender</option><option value="gstin">GSTIN</option>
          </select>
          <label className="sr-only" htmlFor="copilot-invoice-context">Current entity context</label>
          <input
            id="copilot-invoice-context"
            className="input w-48 font-mono text-xs"
            placeholder={contextEntityType === 'company' ? 'Company name or CMP ID' : contextEntityType === 'lender' ? 'Lender name or LND ID' : contextEntityType === 'gstin' ? '15-character GSTIN' : 'Invoice ID'}
            value={contextEntityId}
            onChange={(event) => {
              const value = event.target.value
              setContextEntityId(value)
              if (value.trim()) setSearchParams(contextEntityType === 'invoice' ? { invoiceId: value.trim() } : { entityId: value.trim(), entityType: contextEntityType }, { replace: true })
              else setSearchParams({}, { replace: true })
            }}
          />
          <button className="btn-ghost" onClick={clearConversation} disabled={!messages.length && !error} title="Clear conversation" aria-label="Clear conversation">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <section className="card flex min-h-[30rem] flex-1 flex-col overflow-hidden" aria-label="Copilot conversation">
        <div className="flex-1 space-y-5 overflow-y-auto p-4 md:p-6" aria-live="polite">
          {!messages.length && (
            <div className="mx-auto max-w-2xl py-8">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-blue-800/60 bg-blue-950/60 text-blue-300"><Bot className="h-5 w-5" /></div>
                <div>
                  <h3 className="font-semibold text-slate-100">Ask about verified investigation data</h3>
                  <p className="text-xs text-slate-500">Answers cite application, risk-engine, and Neo4j evidence.</p>
                  {!providerStatus.configured && <p className="mt-1 text-xs text-amber-400">AI reasoning provider is not configured. Evidence-based investigation mode is available.</p>}
                </div>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {suggestions.map((question) => (
                  <button key={question} className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-left text-sm text-slate-300 hover:border-blue-700 hover:text-slate-100" onClick={() => void sendQuestion(question)}>
                    <MessageSquareText className="mr-2 inline h-3.5 w-3.5 text-blue-400" />{question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <article key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : ''}`}>
              {message.role === 'assistant' && <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border border-surface-700 bg-surface-900 text-blue-300"><Bot className="h-4 w-4" /></div>}
              <div className={`min-w-0 max-w-4xl flex-1 ${message.role === 'user' ? 'max-w-2xl rounded-lg border border-blue-800/50 bg-blue-950/40 px-4 py-3' : ''}`}>
                {message.role === 'user' ? (
                  <p className="whitespace-pre-wrap text-sm text-slate-100">{message.content}</p>
                ) : (
                  <>
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-slate-200">Copilot</span>
                      <span className="badge-info text-[10px]">{message.result?.llm_used ? 'AI explanation' : 'Verified data fallback'}</span>
                      {message.result?.latency_ms !== undefined && <span className="text-[10px] text-slate-600">{message.result.latency_ms} ms</span>}
                      <button className="ml-auto rounded p-1 text-slate-500 hover:text-slate-200" onClick={() => void copyAnswer(message)} title="Copy answer" aria-label="Copy answer">
                        {copiedId === message.id ? <Check className="h-3.5 w-3.5" /> : <Clipboard className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-200">{message.content}</p>
                    {!!message.result?.tools.length && <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Executed investigation tools">
                      {message.result.tools.map((tool) => <span key={tool} className="rounded border border-surface-700 px-2 py-1 text-[10px] text-slate-500">{tool}</span>)}
                    </div>}
                    {!!message.result?.findings.length && <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      {message.result.findings.map((finding, index) => <div key={`${finding.kind}-${index}`} className="rounded-md border border-surface-700 bg-surface-900/70 p-3">
                        <div className="text-xs font-semibold text-slate-200">{finding.title}</div>
                        <p className="mt-1 text-xs leading-5 text-slate-400">{finding.detail}</p>
                        {!!finding.evidence_refs?.length && <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Finding citations">
                          {finding.evidence_refs.map((refId) => {
                            const citation = message.result?.citations?.find((item) => item.id === refId)
                            return citation?.href ? <Link key={refId} className="text-[10px] font-mono text-blue-400 hover:text-blue-300" to={citation.href}>[{refId}] Open source</Link> : <span key={refId} className="text-[10px] font-mono text-slate-500">[{refId}]</span>
                          })}
                        </div>}
                        {finding.kind === 'timeline' && Array.isArray(finding.value) && <ol className="mt-2 space-y-2 border-l border-surface-700 pl-3">
                          {(finding.value as Array<{ date: string; label: string; detail: string }>).map((event, eventIndex) => <li key={`${event.label}-${eventIndex}`}>
                            <div className="text-[10px] text-slate-500">{event.date}</div>
                            <div className="text-xs font-medium text-slate-300">{event.label}</div>
                            <div className="text-[11px] text-slate-500">{event.detail}</div>
                          </li>)}
                        </ol>}
                      </div>)}
                    </div>}
                    {!!message.result?.evidence.length && <details open className="mt-3 rounded-md border border-surface-700 bg-surface-900/50 p-3">
                      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-slate-300"><Shield className="h-3.5 w-3.5 text-amber-400" />Evidence and sources ({message.result.evidence.length})</summary>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {message.result.evidence.map((item, index) => <div key={`${item.ref_id}-${item.source_id}-${item.title ?? item.tool}-${index}`} className="rounded border border-surface-700 p-2.5">
                          <div className="text-xs font-medium text-slate-200">{item.title ?? item.source_type}</div>
                          {item.detail && <p className="mt-1 text-xs text-slate-400">{item.detail}</p>}
                          <div className="mt-1 text-[10px] text-slate-600">[{item.ref_id}] {item.source_type} · {item.source_id}{item.confidence !== undefined ? ` · ${Math.round(item.confidence * 100)}%` : ''}</div>
                          {item.href && <Link className="mt-1 inline-block text-[10px] text-blue-400 hover:text-blue-300" to={item.href}>Open evidence</Link>}
                        </div>)}
                      </div>
                    </details>}
                    {!!message.result?.entities.length && <div className="mt-3 flex flex-wrap gap-2">
                      {message.result.entities.map((entity) => <Link key={`${entity.type}-${entity.id}`} className="rounded-full border border-surface-700 px-2.5 py-1 text-xs text-blue-300 hover:border-blue-700" to={entity.href}>{entity.label}</Link>)}
                    </div>}
                    {!!message.result?.actions.length && <div className="mt-3 flex flex-wrap gap-2">
                      {message.result.actions.map((action) => <Link key={`${action.label}-${action.href}`} className="btn-ghost text-xs" to={action.href}>{action.label}</Link>)}
                      {message.result.report_text && <button className="btn-ghost text-xs" onClick={() => downloadReport(message)}><Download className="h-3.5 w-3.5" /> Download Report</button>}
                    </div>}
                    {message.result?.fallback_reason === 'ai_provider_unavailable' && <p className="mt-2 text-xs text-amber-400">AI reasoning service is temporarily unavailable. Evidence-based investigation is still available.</p>}
                    {message.result?.fallback_reason === 'unsafe_query_rejected' && <p className="mt-2 text-xs text-amber-400">That request is not supported by the approved read-only investigation tools.</p>}
                  </>
                )}
              </div>
            </article>
          ))}
          {loading && <div className="flex items-center gap-2 text-xs text-blue-300"><Loader2 className="h-4 w-4 animate-spin" />Checking approved investigation tools…</div>}
          {error && <div role="alert" className="rounded-md border border-red-900/70 bg-red-950/30 px-3 py-2 text-sm text-red-300">{error}</div>}
        </div>

        {!!messages.length && <div className="border-t border-surface-700 px-4 py-3">
          <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
            {suggestions.slice(0, 4).map((question) => <button key={question} className="whitespace-nowrap rounded-full border border-surface-700 px-2.5 py-1 text-[10px] text-slate-400 hover:text-slate-200" onClick={() => void sendQuestion(question)} disabled={loading}>{question}</button>)}
          </div>
        </div>}
        <form className="flex items-end gap-2 border-t border-surface-700 p-3 md:p-4" onSubmit={(event) => { event.preventDefault(); void sendQuestion() }}>
          <label className="sr-only" htmlFor="copilot-message">Ask the investigation copilot</label>
          <textarea id="copilot-message" className="input min-h-11 max-h-36 flex-1 resize-y" placeholder={contextEntityId ? `Ask about ${contextEntityId}…` : 'Ask about an invoice, company, lender, or risk finding…'} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendQuestion() } }} maxLength={1200} />
          <button className="btn-primary h-11" type="submit" disabled={!draft.trim() || loading} aria-label="Send question"><Send className="h-4 w-4" /><span className="hidden sm:inline">Send</span></button>
          {!!lastQuestion && <button className="btn-ghost h-11" type="button" onClick={regenerate} disabled={loading} title="Regenerate last answer" aria-label="Regenerate last answer"><RotateCcw className="h-4 w-4" /></button>}
        </form>
      </section>

      {generatedReport && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
        <section role="dialog" aria-modal="true" aria-labelledby="copilot-report-title" className="card flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden">
          <div className="card-header flex items-center justify-between">
            <div>
              <h3 id="copilot-report-title" className="text-sm font-semibold text-slate-100">Investigation Report</h3>
              <p className="mt-1 text-xs text-slate-500">Generated from verified application findings</p>
            </div>
            <button className="btn-ghost text-xs" onClick={() => setGeneratedReport(null)}>Close</button>
          </div>
          <pre className="m-4 overflow-auto whitespace-pre-wrap rounded border border-surface-700 bg-surface-950 p-4 text-xs leading-5 text-slate-300">{generatedReport.content}</pre>
          <div className="flex justify-end gap-2 border-t border-surface-700 p-3">
            <button className="btn-ghost text-xs" onClick={() => void navigator.clipboard.writeText(generatedReport.content)}><Clipboard className="h-3.5 w-3.5" /> Copy Report</button>
            <button className="btn-primary text-xs" onClick={() => saveReport(generatedReport.invoiceId)}><Download className="h-3.5 w-3.5" /> Save .txt</button>
          </div>
        </section>
      </div>}
    </div>
  )
}
