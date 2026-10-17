import type { ReactNode } from 'react'
import { cn } from '@/common/utils/cn'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'accent'
const tones: Record<Tone, string> = {
  neutral: 'bg-bg text-muted border-line-strong', success: 'bg-success-soft text-success border-success',
  warning: 'bg-warning-soft text-warning border-warning', danger: 'bg-danger-soft text-danger border-danger',
  info: 'bg-info-soft text-info border-info', accent: 'bg-accent-soft text-accent border-accent',
}
/** Always icon + text: colour is never the only signal (FE-DS-03). */
export function Badge({ tone = 'neutral', icon, children, className }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium', tones[tone], className)}>
      {icon && <span aria-hidden className="inline-flex">{icon}</span>}{children}
    </span>
  )
}
