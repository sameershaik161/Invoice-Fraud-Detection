import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { checkDuplicateInvoice, createInvoice } from '@/services/api'

interface LineItemDraft {
  description: string
  hsn_code: string
  quantity: number
  unit_price: number
  total_amount: number
}

interface FinancingDraft {
  lender_id: string
  financing_amount: number
  financing_date: string
  financing_status: string
}

const emptyLineItem = (): LineItemDraft => ({
  description: '',
  hsn_code: '',
  quantity: 0,
  unit_price: 0,
  total_amount: 0,
})

const emptyFinancing = (): FinancingDraft => ({
  lender_id: '',
  financing_amount: 0,
  financing_date: '',
  financing_status: 'APPROVED',
})

export default function AddInvoicePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    invoice_id: '',
    invoice_date: '',
    invoice_amount: 0,
    currency: 'INR',
    invoice_type: 'PURCHASE',
    invoice_description: '',
    seller_company_id: '',
    seller_company_name: '',
    seller_gstin: '',
    buyer_company_id: '',
    buyer_company_name: '',
    buyer_gstin: '',
    financing: [] as FinancingDraft[],
    delivery: {
      eway_bill_no: '',
      delivery_status: 'GENERATED',
      delivery_date: '',
      additional_metadata: '',
    },
    line_items: [emptyLineItem()],
  })
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ type: 'error' | 'success' | 'info'; text: string } | null>(null)
  const [duplicateResult, setDuplicateResult] = useState<any>(null)
  const [continueSimilar, setContinueSimilar] = useState(false)

  const totalLineValue = useMemo(
    () => form.line_items.reduce((sum, item) => sum + (Number(item.total_amount) || Number(item.quantity) * Number(item.unit_price)), 0),
    [form.line_items],
  )

  const invalidateDuplicateCheck = () => {
    setDuplicateResult(null)
    setContinueSimilar(false)
  }

  const validateRequiredFields = () => {
    if (!form.invoice_id.trim() || !form.invoice_date || Number(form.invoice_amount) <= 0 || !form.seller_company_id.trim() || !form.buyer_company_id.trim()) {
      setMessage({ type: 'error', text: 'Enter an invoice ID, date, positive amount, seller ID, and buyer ID before verification.' })
      return false
    }
    return true
  }

  const updateField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    invalidateDuplicateCheck()
    setForm((current) => ({ ...current, [key]: value }))
  }

  const updateFinancing = (index: number, key: keyof FinancingDraft, value: string | number) => {
    invalidateDuplicateCheck()
    setForm((current) => ({
      ...current,
      financing: current.financing.map((item, idx) => idx === index ? { ...item, [key]: value } : item),
    }))
  }

  const updateLineItem = (index: number, key: keyof LineItemDraft, value: string | number) => {
    invalidateDuplicateCheck()
    setForm((current) => {
      const nextItems = current.line_items.map((item, idx) => {
        if (idx !== index) return item
        const updated = { ...item, [key]: value }
        if (key === 'quantity' || key === 'unit_price') {
          updated.total_amount = Number(updated.quantity) * Number(updated.unit_price)
        }
        return updated
      })
      return { ...current, line_items: nextItems }
    })
  }

  const handleCheckDuplicates = async () => {
    if (!validateRequiredFields()) return
    setChecking(true)
    setContinueSimilar(false)
    setMessage(null)
    try {
      const response = await checkDuplicateInvoice({
        ...form,
        invoice_amount: Number(form.invoice_amount),
        allow_similar: true,
      })
      setDuplicateResult(response.data)
      if (response.data.result === 'EXACT_DUPLICATE') {
        setMessage({ type: 'error', text: 'Duplicate invoice detected; the record already exists in the system.' })
      } else if (response.data.result === 'POSSIBLE_DUPLICATE') {
        setMessage({ type: 'error', text: 'Normalized invoice ID matches an existing record. Creation is blocked to prevent a duplicate.' })
      } else if (response.data.result === 'SIMILAR_INVOICE') {
        setMessage({ type: 'info', text: `Potential duplicate found: ${response.data.similar_invoice_id || 'existing record'}. Review before continuing.` })
      } else {
        setMessage({ type: 'success', text: 'No exact duplicate found. The invoice can be created.' })
      }
    } catch (error: any) {
      const detail = error.response?.data?.detail
      setDuplicateResult(null)
      setMessage({ type: 'error', text: typeof detail === 'string' ? detail : 'Duplicate check failed. The invoice has not been verified.' })
    } finally {
      setChecking(false)
    }
  }

  const handleSubmit = async () => {
    if (!validateRequiredFields()) return
    if (!duplicateResult) {
      setMessage({ type: 'error', text: 'Check for duplicates before submitting this invoice.' })
      return
    }
    if (duplicateResult.result === 'EXACT_DUPLICATE' || duplicateResult.result === 'POSSIBLE_DUPLICATE') {
      setMessage({ type: 'error', text: 'This invoice matches an existing record and cannot be submitted from this form.' })
      return
    }
    if (duplicateResult.result === 'SIMILAR_INVOICE' && !continueSimilar) {
      setMessage({ type: 'info', text: 'Review the similar invoice and explicitly confirm before continuing.' })
      return
    }
    setSubmitting(true)
    setMessage(null)
    try {
      const response = await createInvoice({
        ...form,
        invoice_amount: Number(form.invoice_amount),
        financing: form.financing.filter((item) => item.lender_id || item.financing_amount > 0),
        line_items: form.line_items.filter((item) => item.description || item.hsn_code || item.quantity > 0),
        allow_similar: duplicateResult.result === 'SIMILAR_INVOICE' && continueSimilar,
      })
      setMessage({ type: 'success', text: `Invoice ${response.data.invoice_id} created successfully.` })
      navigate(`/investigation/${response.data.invoice_id}`)
    } catch (error: any) {
      const payload = error.response?.data
      const detail = payload?.detail
      const msg = typeof detail === 'string' ? detail : payload?.message || 'Invoice creation failed.'
      setMessage({ type: 'error', text: msg })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Add New Invoice</h2>
          <p className="text-sm text-slate-500">Validate, duplicate-check, and insert a verified invoice into the live system.</p>
        </div>
      </div>

      {message && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${message.type === 'error' ? 'border-red-800 bg-red-950/40 text-red-200' : message.type === 'success' ? 'border-green-800 bg-green-950/40 text-green-200' : 'border-blue-800 bg-blue-950/40 text-blue-200'}`}>
          {message.type === 'error' ? <AlertTriangle className="mr-2 inline h-4 w-4" /> : message.type === 'success' ? <CheckCircle2 className="mr-2 inline h-4 w-4" /> : <ShieldCheck className="mr-2 inline h-4 w-4" />}
          {message.text}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-5">
          <section className="card p-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Invoice Identity</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm text-slate-300">
                <span>Invoice ID <span className="text-red-700">*</span></span>
                <input required className="input" value={form.invoice_id} onChange={(e) => updateField('invoice_id', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300">
                <span>Invoice Date <span className="text-red-700">*</span></span>
                <input required type="date" className="input" value={form.invoice_date} onChange={(e) => updateField('invoice_date', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300">
                <span>Amount <span className="text-red-700">*</span></span>
                <input required min="0.01" type="number" step="0.01" className="input" value={form.invoice_amount || ''} onChange={(e) => updateField('invoice_amount', Number(e.target.value))} />
              </label>
              <label className="space-y-1 text-sm text-slate-300">
                <span>Currency</span>
                <input className="input" value={form.currency} onChange={(e) => updateField('currency', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300 md:col-span-2">
                <span>Invoice Description</span>
                <input className="input" value={form.invoice_description} onChange={(e) => updateField('invoice_description', e.target.value)} />
              </label>
            </div>
          </section>

          <section className="card p-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Seller</h3>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm text-slate-300">
                <span>Company ID <span className="text-red-700">*</span></span>
                <input required className="input" value={form.seller_company_id} onChange={(e) => updateField('seller_company_id', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300 md:col-span-2">
                <span>Company Name</span>
                <input className="input" value={form.seller_company_name} onChange={(e) => updateField('seller_company_name', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300 md:col-span-3">
                <span>GSTIN</span>
                <input className="input" value={form.seller_gstin} onChange={(e) => updateField('seller_gstin', e.target.value)} />
              </label>
            </div>
          </section>

          <section className="card p-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Buyer</h3>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm text-slate-300">
                <span>Company ID <span className="text-red-700">*</span></span>
                <input required className="input" value={form.buyer_company_id} onChange={(e) => updateField('buyer_company_id', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300 md:col-span-2">
                <span>Company Name</span>
                <input className="input" value={form.buyer_company_name} onChange={(e) => updateField('buyer_company_name', e.target.value)} />
              </label>
              <label className="space-y-1 text-sm text-slate-300 md:col-span-3">
                <span>GSTIN</span>
                <input className="input" value={form.buyer_gstin} onChange={(e) => updateField('buyer_gstin', e.target.value)} />
              </label>
            </div>
          </section>

          <section className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Financing</h3>
              <button className="btn-ghost text-xs" onClick={() => setForm((current) => ({ ...current, financing: [...current.financing, emptyFinancing()] }))}><Plus className="mr-1 inline h-3.5 w-3.5" /> Add Financing Record</button>
            </div>
            <div className="space-y-3">
              {form.financing.map((item, index) => (
                <div key={`${item.lender_id || 'new'}-${index}`} className="grid gap-3 rounded-md border border-surface-700 bg-surface-900/50 p-3 md:grid-cols-5">
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Lender ID</span>
                    <input className="input" value={item.lender_id} onChange={(e) => updateFinancing(index, 'lender_id', e.target.value)} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Amount</span>
                    <input type="number" step="0.01" className="input" value={item.financing_amount} onChange={(e) => updateFinancing(index, 'financing_amount', Number(e.target.value))} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Date</span>
                    <input type="date" className="input" value={item.financing_date} onChange={(e) => updateFinancing(index, 'financing_date', e.target.value)} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Status</span>
                    <select className="input" value={item.financing_status} onChange={(e) => updateFinancing(index, 'financing_status', e.target.value)}>
                      <option value="APPROVED">APPROVED</option>
                      <option value="DISBURSED">DISBURSED</option>
                      <option value="PENDING">PENDING</option>
                    </select>
                  </label>
                  <div className="flex items-end justify-end">
                    {form.financing.length > 1 && <button className="btn-ghost text-xs" onClick={() => setForm((current) => ({ ...current, financing: current.financing.filter((_, idx) => idx !== index) }))}><Trash2 className="h-3.5 w-3.5" /></button>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="card p-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Delivery</h3>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm text-slate-300">
                <span>E-Way Bill ID</span>
                <input className="input" value={form.delivery.eway_bill_no} onChange={(e) => { invalidateDuplicateCheck(); setForm((current) => ({ ...current, delivery: { ...current.delivery, eway_bill_no: e.target.value } })) }} />
              </label>
              <label className="space-y-1 text-sm text-slate-300">
                <span>Delivery Status</span>
                <select className="input" value={form.delivery.delivery_status} onChange={(e) => { invalidateDuplicateCheck(); setForm((current) => ({ ...current, delivery: { ...current.delivery, delivery_status: e.target.value } })) }}>
                  <option value="GENERATED">GENERATED</option>
                  <option value="IN_TRANSIT">IN_TRANSIT</option>
                  <option value="DELIVERED">DELIVERED</option>
                </select>
              </label>
              <label className="space-y-1 text-sm text-slate-300">
                <span>Delivery Date</span>
                <input type="date" className="input" value={form.delivery.delivery_date} onChange={(e) => { invalidateDuplicateCheck(); setForm((current) => ({ ...current, delivery: { ...current.delivery, delivery_date: e.target.value } })) }} />
              </label>
            </div>
          </section>

          <section className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Line Items</h3>
              <button className="btn-ghost text-xs" onClick={() => setForm((current) => ({ ...current, line_items: [...current.line_items, emptyLineItem()] }))}><Plus className="mr-1 inline h-3.5 w-3.5" /> Add Line Item</button>
            </div>
            <div className="space-y-3">
              {form.line_items.map((item, index) => (
                <div key={`${item.description || 'line'}-${index}`} className="grid gap-3 rounded-md border border-surface-700 bg-surface-900/50 p-3 md:grid-cols-6">
                  <label className="space-y-1 text-xs text-slate-300 md:col-span-2">
                    <span>Description</span>
                    <input className="input" value={item.description} onChange={(e) => updateLineItem(index, 'description', e.target.value)} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>HSN</span>
                    <input className="input" value={item.hsn_code} onChange={(e) => updateLineItem(index, 'hsn_code', e.target.value)} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Qty</span>
                    <input type="number" step="0.01" className="input" value={item.quantity} onChange={(e) => updateLineItem(index, 'quantity', Number(e.target.value))} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Price</span>
                    <input type="number" step="0.01" className="input" value={item.unit_price} onChange={(e) => updateLineItem(index, 'unit_price', Number(e.target.value))} />
                  </label>
                  <label className="space-y-1 text-xs text-slate-300">
                    <span>Total</span>
                    <input type="number" step="0.01" className="input" value={item.total_amount} onChange={(e) => updateLineItem(index, 'total_amount', Number(e.target.value))} />
                  </label>
                  <div className="flex items-end justify-end">
                    {form.line_items.length > 1 && <button className="btn-ghost text-xs" onClick={() => setForm((current) => ({ ...current, line_items: current.line_items.filter((_, idx) => idx !== index) }))}><Trash2 className="h-3.5 w-3.5" /></button>}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <div className="card p-5">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">Review</h3>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="flex justify-between"><span>Invoice total</span><span className="font-mono text-slate-100">₹{Number(form.invoice_amount || 0).toLocaleString('en-IN')}</span></div>
              <div className="flex justify-between"><span>Line total</span><span className="font-mono text-slate-100">₹{totalLineValue.toLocaleString('en-IN')}</span></div>
              <div className="flex justify-between"><span>Financing entries</span><span className="font-mono text-slate-100">{form.financing.length}</span></div>
            </div>
          </div>

          {duplicateResult && (
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">Duplicate Check</h3>
              <p className={`text-sm font-semibold ${duplicateResult.result === 'EXACT_DUPLICATE' || duplicateResult.result === 'POSSIBLE_DUPLICATE' ? 'text-red-800' : duplicateResult.result === 'SIMILAR_INVOICE' ? 'text-amber-800' : 'text-green-800'}`}>
                {duplicateResult.result === 'EXACT_DUPLICATE' ? 'Duplicate invoice detected' : duplicateResult.result === 'POSSIBLE_DUPLICATE' ? 'Normalized invoice ID match' : duplicateResult.result === 'SIMILAR_INVOICE' ? 'Potential duplicate' : 'No duplicate found'}
              </p>
              <p className="mt-2 text-xs text-slate-600">{duplicateResult.similar_invoice_id ? `Similar invoice: ${duplicateResult.similar_invoice_id} · Similarity ${Math.round((duplicateResult.similarity_score ?? 0) * 100)}%` : duplicateResult.resolved_invoice_id ? `Existing record: ${duplicateResult.resolved_invoice_id}` : duplicateResult.existing_invoice ? `Existing record: ${duplicateResult.existing_invoice.invoice_id}` : 'No existing match was returned by the duplicate check.'}</p>
              {duplicateResult.existing_invoice && <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-surface-700 pt-3 text-xs">
                <div><dt className="text-slate-500">Invoice date</dt><dd className="mt-0.5 text-slate-800">{duplicateResult.existing_invoice.invoice_date || 'Not available'}</dd></div>
                <div><dt className="text-slate-500">Amount</dt><dd className="mt-0.5 font-mono text-slate-800">{Number(duplicateResult.existing_invoice.net_amount).toLocaleString('en-IN')} {duplicateResult.existing_invoice.currency || ''}</dd></div>
                <div><dt className="text-slate-500">Seller</dt><dd className="mt-0.5 break-all text-slate-800">{duplicateResult.existing_invoice.seller_id || 'Not available'}</dd></div>
                <div><dt className="text-slate-500">Buyer</dt><dd className="mt-0.5 break-all text-slate-800">{duplicateResult.existing_invoice.buyer_id || 'Not available'}</dd></div>
                <div><dt className="text-slate-500">Risk level</dt><dd className="mt-0.5 text-slate-600">Not available from duplicate check</dd></div>
                <div><dt className="text-slate-500">Financing</dt><dd className="mt-0.5 text-slate-600">Not available from duplicate check</dd></div>
              </dl>}
              {duplicateResult.result === 'SIMILAR_INVOICE' && !!duplicateResult.matching_evidence?.length && <div className="mt-3 border-t border-surface-700 pt-3"><div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Matching evidence</div><ul className="mt-1 list-inside list-disc space-y-1 text-xs text-slate-700">{duplicateResult.matching_evidence.map((item: string) => <li key={item}>{item}</li>)}</ul></div>}
              {(duplicateResult.existing_invoice?.invoice_id || duplicateResult.similar_invoice_id || duplicateResult.resolved_invoice_id) && <button className="mt-3 text-xs font-medium text-blue-800 hover:underline" onClick={() => navigate(`/investigation/${duplicateResult.existing_invoice?.invoice_id || duplicateResult.similar_invoice_id || duplicateResult.resolved_invoice_id}`)}>Open matching investigation</button>}
              {duplicateResult.result === 'SIMILAR_INVOICE' && <button className="btn-ghost mt-3 w-full justify-center" onClick={() => { setContinueSimilar(true); setMessage({ type: 'info', text: 'Similar invoice acknowledged. Submission is enabled; the new invoice will not be classified as fraud.' }) }}>Continue Anyway</button>}
            </div>
          )}

          <div className="card p-5">
            <button className="btn-ghost w-full justify-center" onClick={() => navigate('/invoices')}>Cancel</button>
            <button className="btn-primary mt-2 w-full justify-center" onClick={handleCheckDuplicates} disabled={checking || submitting}><ShieldCheck className="h-4 w-4" />{checking ? 'Checking...' : 'Check for Duplicates'}</button>
            <button className="btn-primary mt-2 w-full justify-center" onClick={handleSubmit} disabled={submitting || checking || !duplicateResult || duplicateResult.result === 'EXACT_DUPLICATE' || duplicateResult.result === 'POSSIBLE_DUPLICATE' || (duplicateResult.result === 'SIMILAR_INVOICE' && !continueSimilar)}>{submitting ? 'Submitting...' : 'Submit Invoice'}</button>
          </div>
        </aside>
      </div>
    </div>
  )
}
