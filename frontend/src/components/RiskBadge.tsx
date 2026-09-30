import clsx from 'clsx'
import type { RiskLevel } from '@/types'
import { getRiskBadgeClass } from '@/utils/format'
import { AlertTriangle, CheckCircle, AlertOctagon, Shield } from 'lucide-react'

interface Props {
  level?: RiskLevel
  showIcon?: boolean
  size?: 'sm' | 'md' | 'lg'
}

const icons = {
  LOW: CheckCircle,
  MEDIUM: AlertTriangle,
  HIGH: AlertTriangle,
  CRITICAL: AlertOctagon,
}

export default function RiskBadge({ level, showIcon = true, size = 'md' }: Props) {
  if (!level) return <span className="badge-info">UNKNOWN</span>

  const Icon = icons[level] ?? Shield
  const cls = getRiskBadgeClass(level)
  const textSize = size === 'lg' ? 'text-sm px-3 py-1' : size === 'sm' ? 'text-[10px]' : ''

  return (
    <span className={clsx(cls, textSize)}>
      {showIcon && <Icon className={size === 'lg' ? 'w-4 h-4' : 'w-3 h-3'} />}
      {level}
    </span>
  )
}
