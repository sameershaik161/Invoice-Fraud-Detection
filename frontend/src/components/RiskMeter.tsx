import { motion } from 'framer-motion'
import type { RiskLevel } from '@/types'
import clsx from 'clsx'

interface Props {
  score: number
  level: RiskLevel
  size?: 'sm' | 'lg'
}

const strokeColors: Record<RiskLevel, string> = {
  LOW: '#22c55e',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
  CRITICAL: '#dc2626',
}

export default function RiskMeter({ score, level, size = 'lg' }: Props) {
  const radius = size === 'lg' ? 64 : 40
  const stroke = size === 'lg' ? 8 : 5
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - score / 100)
  const color = strokeColors[level]
  const svgSize = (radius + stroke) * 2

  return (
    <div className="flex flex-col items-center gap-2">
      <svg
        width={svgSize}
        height={svgSize}
        viewBox={`0 0 ${svgSize} ${svgSize}`}
        className="-rotate-90"
        aria-label={`Risk score: ${score} out of 100`}
      >
        {/* Track */}
        <circle
          cx={svgSize / 2}
          cy={svgSize / 2}
          r={radius}
          fill="none"
          stroke="#1a2540"
          strokeWidth={stroke}
        />
        {/* Progress */}
        <motion.circle
          cx={svgSize / 2}
          cy={svgSize / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
      </svg>
      <div className="text-center -mt-2">
        <motion.div
          className={clsx(
            'font-bold leading-none',
            size === 'lg' ? 'text-5xl' : 'text-2xl'
          )}
          style={{ color }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          {score}
        </motion.div>
        <div className="text-slate-500 text-xs mt-1">/ 100</div>
      </div>
    </div>
  )
}
