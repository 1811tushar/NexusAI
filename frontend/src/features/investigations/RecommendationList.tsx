import { RiskBadge } from '@/common/components/RiskBadge'
import { Badge, type Tone } from '@/common/components/ui/Badge'
import type { ActionLogDTO, ApprovalDTO, RecommendationDTO } from './types'

export function recommendationStatus(rec: RecommendationDTO, approvals: ApprovalDTO[], actions: ActionLogDTO[]): { label: string; tone: Tone } | null {
  if (!rec.actionKey) return null
  const ap = approvals.find((a) => a.actionKey === rec.actionKey)
  if (ap) {
    if (ap.status === 'PENDING') return { label: 'Pending approval', tone: 'warning' }
    if (ap.status === 'REJECTED') return { label: 'Rejected', tone: 'danger' }
    if (ap.status === 'EXPIRED') return { label: 'Expired', tone: 'neutral' }
    const act = actions.find((a) => a.approvalId === ap.id)
    if (!act) return { label: 'Approved', tone: 'info' }
    return act.status === 'FAILED' ? { label: 'Failed', tone: 'danger' } : { label: 'Executed (simulated)', tone: 'success' }
  }
  // Low-risk actions run automatically. The log has no action key, so this is matched on "an automatic action ran".
  return actions.some((a) => a.automatic && a.status === 'EXECUTED') ? { label: 'Executed (simulated)', tone: 'success' } : null
}
export function RecommendationList({ recommendations, approvals, actions }: { recommendations: RecommendationDTO[]; approvals: ApprovalDTO[]; actions: ActionLogDTO[] }) {
  if (recommendations.length === 0) return <p className="text-sm text-muted">No recommendations were made.</p>
  return (
    <ul className="space-y-3">{recommendations.map((r) => { const s = recommendationStatus(r, approvals, actions); return (
      <li key={r.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface p-3">
        <p className="min-w-0 flex-1">{r.text}</p><RiskBadge risk={r.risk} />{s && <Badge tone={s.tone}>{s.label}</Badge>}
      </li>) })}</ul>
  )
}
