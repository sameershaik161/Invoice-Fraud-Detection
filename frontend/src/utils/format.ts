import type { RiskLevel, RecommendedAction } from '@/types'

export function formatCurrency(amount: number, currency = 'INR'): string {
  if (amount >= 1_00_00_000) {
    return `₹${(amount / 1_00_00_000).toFixed(2)} Cr`
  }
  if (amount >= 1_00_000) {
    return `₹${(amount / 1_00_000).toFixed(2)} L`
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatDate(dateStr: string): string {
  if (!dateStr || dateStr === 'NaT') return '—'
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export function getRiskColor(level?: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'text-green-400'
    case 'MEDIUM': return 'text-amber-400'
    case 'HIGH': return 'text-red-400'
    case 'CRITICAL': return 'text-red-300'
    default: return 'text-slate-400'
  }
}

export function getRiskBadgeClass(level?: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'badge-low'
    case 'MEDIUM': return 'badge-medium'
    case 'HIGH': return 'badge-high'
    case 'CRITICAL': return 'badge-critical'
    default: return 'badge-info'
  }
}

export function getRiskBg(level?: RiskLevel): string {
  switch (level) {
    case 'LOW': return 'border-green-800/50 bg-green-950/10'
    case 'MEDIUM': return 'border-amber-800/50 bg-amber-950/10'
    case 'HIGH': return 'border-red-800/50 bg-red-950/20'
    case 'CRITICAL': return 'border-red-700 bg-red-950/30'
    default: return 'border-surface-600'
  }
}

export function getActionLabel(action: RecommendedAction): string {
  switch (action) {
    case 'PROCEED': return 'Proceed'
    case 'MANUAL_REVIEW': return 'Manual Review'
    case 'ENHANCED_VERIFICATION': return 'Enhanced Verification'
    case 'HOLD_PAYOUT': return 'Hold Payout'
    default: return action
  }
}

export function getActionColor(action: RecommendedAction): string {
  switch (action) {
    case 'PROCEED': return 'text-green-400'
    case 'MANUAL_REVIEW': return 'text-amber-400'
    case 'ENHANCED_VERIFICATION': return 'text-orange-400'
    case 'HOLD_PAYOUT': return 'text-red-400'
    default: return 'text-slate-400'
  }
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}
