import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
import { cn } from '@/common/utils/cn'
import { agentLabel } from './labels'
import type { PlanStep, StepStatus } from './types'

const meta: Record<StepStatus, { Icon: typeof Circle; label: string; cls: string }> = {
  PENDING: { Icon: Circle, label: 'Pending', cls: 'text-muted' },
  RUNNING: { Icon: Loader2, label: 'Running', cls: 'text-info' },
  DONE: { Icon: CheckCircle2, label: 'Done', cls: 'text-success' },
  FAILED: { Icon: XCircle, label: 'Failed', cls: 'text-danger' },
}
/** Icon + text per status, so state is never colour-only. */
export function PlanChecklist({ steps }: { steps: PlanStep[] }) {
  if (steps.length === 0) return <p className="text-sm text-muted">The planner has not produced a plan yet.</p>
  return (
    <ol aria-label="Investigation plan" className="space-y-3">
      {steps.map((s) => {
        const m = meta[s.status]
        return (
          <li key={s.id} className="flex gap-2">
            <m.Icon className={cn('mt-0.5 h-4 w-4 shrink-0', m.cls, s.status === 'RUNNING' && 'animate-spin')} aria-hidden />
            <div><p className="text-sm">{s.description}</p><p className="text-xs text-muted">{agentLabel(s.agent)}, {m.label}</p></div>
          </li>
        )
      })}
    </ol>
  )
}
