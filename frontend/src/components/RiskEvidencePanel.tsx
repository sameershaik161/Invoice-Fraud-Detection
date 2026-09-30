import { useEffect, useState } from 'react'
import type { EvidenceItem } from '@/types'

interface RiskEvidencePanelProps {
  evidence: EvidenceItem[]
}

const severityStyles: Record<EvidenceItem['severity'], string> = {
  critical: 'evidence-critical',
  warning: 'evidence-warning',
  info: 'evidence-info',
  safe: 'evidence-safe',
}

export default function RiskEvidencePanel({ evidence }: RiskEvidencePanelProps) {
  const [selected, setSelected] = useState<EvidenceItem | null>(null)

  useEffect(() => {
    setSelected(evidence[0] ?? null)
  }, [evidence])

  if (!evidence.length) {
    return <div className="card"><div className="card-body text-sm text-slate-500">No evidence signals available for this invoice.</div></div>
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {evidence.map((item) => (
          <button
            key={`${item.title}-${item.step}`}
            className={`w-full text-left rounded-md border p-3 transition-colors ${selected?.title === item.title ? severityStyles[item.severity] : 'border-surface-700 bg-white text-slate-700 hover:border-surface-600'}`}
            onClick={() => setSelected(item)}
          >
            <div className="text-xs uppercase tracking-wider text-slate-400">Signal {item.step}</div>
            <div className="mt-1 font-semibold text-sm">{item.title}</div>
            <div className="mt-1 text-xs opacity-80">{item.detail}</div>
          </button>
        ))}
      </div>

      {selected && (
          <div className={`rounded-md border p-4 ${severityStyles[selected.severity]}`}>
          <div className="text-[10px] uppercase tracking-wider opacity-80">Selected evidence</div>
          <div className="mt-2 text-lg font-semibold">{selected.title}</div>
          <p className="mt-2 text-sm leading-6 opacity-90">{selected.detail}</p>
        </div>
      )}
    </div>
  )
}
