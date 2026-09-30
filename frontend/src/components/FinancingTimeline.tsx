import type { TimelineEvent } from '@/types'

interface FinancingTimelineProps {
  events: TimelineEvent[]
}

export default function FinancingTimeline({ events }: FinancingTimelineProps) {
  if (!events.length) {
    return <div className="card"><div className="card-body text-sm text-slate-500">No financing timeline available for this invoice.</div></div>
  }

  return (
    <div className="relative pl-3">
      <div className="absolute left-4 top-2 bottom-2 w-px bg-surface-700" />
      <div className="space-y-6">
        {events.map((event, index) => (
          <div key={`${event.label}-${index}`} className="relative pl-8">
            <div className={`absolute left-0 top-1.5 h-3 w-3 rounded-full border ${event.severity === 'warning' ? 'bg-red-500 border-red-400' : event.severity === 'info' ? 'bg-blue-500 border-blue-400' : 'bg-green-500 border-green-400'}`} />
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{event.date || 'Date unavailable'}</div>
                <div className="mt-1 text-sm font-semibold text-slate-100">{event.label}</div>
                <div className="mt-1 text-xs text-slate-400">{event.detail}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
