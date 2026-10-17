import { AlertTriangle } from 'lucide-react'
import { cn } from '@/common/utils/cn'

interface Props { value: number | null; threshold?: number; lowConfidence?: boolean; className?: string }
/** value 0..1. Threshold marker + text label so meaning never relies on colour (FE-DS-03). */
export function ConfidenceGauge({ value, threshold = 0.7, lowConfidence, className }: Props) {
  if (value === null) return <span className="text-sm text-muted">Confidence pending</span>
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const low = lowConfidence ?? value < threshold
  return (
    <div className={cn('w-full max-w-xs', className)}>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">Confidence {pct}%</span>
        {low && <span className="inline-flex items-center gap-1 text-warning"><AlertTriangle className="h-3 w-3" aria-hidden />Low confidence</span>}
      </div>
      <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
        aria-valuetext={`${pct}% confidence, threshold ${Math.round(threshold * 100)}%${low ? ', low confidence' : ''}`}
        className="relative mt-1 h-2 rounded-sm bg-line">
        <div className={cn('h-full rounded-sm', low ? 'bg-warning' : 'bg-success')} style={{ width: `${pct}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-ink" style={{ left: `${threshold * 100}%` }} aria-hidden />
      </div>
    </div>
  )
}
