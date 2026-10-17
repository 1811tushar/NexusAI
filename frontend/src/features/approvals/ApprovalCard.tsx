import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { RiskBadge } from '@/common/components/RiskBadge'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Badge } from '@/common/components/ui/Badge'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { useAuthStore } from '@/features/auth/authStore'
import { actionLabel, expiryText, formatParam, humanizeKey, relativeTime } from '@/features/investigations/labels'
import type { ApprovalDTO } from '@/features/investigations/types'
import { DecisionDialog } from './DecisionDialog'
import { decisionBlockReason } from './decisionRules'

export function ApprovalCard({ approval: a }: { approval: ApprovalDTO }) {
  const user = useAuthStore((s) => s.user)
  const [open, setOpen] = useState(false)
  if (!user) return null
  const readOnly = decisionBlockReason({ role: user.role, userId: user.id, status: a.status })
  return (
    <Card>
      <article aria-labelledby={`ap-${a.id}`} className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div><h2 id={`ap-${a.id}`} className="font-semibold">{a.title}</h2><p className="text-xs text-muted">{actionLabel[a.actionType]}</p></div>
          <div className="flex gap-2"><RiskBadge risk={a.risk} /><StatusBadge status={a.status} /></div>
        </div>
        <p className="text-sm">{a.description}</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">{Object.entries(a.params).map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{humanizeKey(k)}</dt><dd>{formatParam(k, v)}</dd></div>))}</dl>
        <p className="text-sm"><b>Why:</b> {a.rationale}</p>
        <div className="flex flex-wrap items-center gap-4"><ConfidenceGauge value={a.confidence} className="max-w-48" /><span className="text-xs text-muted">Supporting investigation confidence</span></div>
        <p className="text-sm text-muted">From <Link className="text-accent underline" to={`/investigations/${a.investigationId}`}>{a.investigationQuestion}</Link></p>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted"><span>Requested {relativeTime(a.requestedAt)}</span>{a.status === 'PENDING' && <Badge tone="warning">{expiryText(a.requestedAt)}</Badge>}
          {a.decidedBy && <span>Decided by {a.decidedBy.displayName}{a.comment ? `: ${a.comment}` : ''}</span>}</div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/approvals/${a.id}`} className="inline-flex h-8 items-center rounded-md border border-line-strong px-3 text-sm hover:bg-accent-soft">View evidence ({a.evidenceKeys.length})</Link>
          {a.status === 'PENDING' && (readOnly ? <p className="text-sm text-muted">{readOnly}</p> : <Button size="sm" onClick={() => setOpen(true)}>Review and decide</Button>)}
        </div>
        <DecisionDialog approval={a} role={user.role} userId={user.id} open={open} onOpenChange={setOpen} />
      </article>
    </Card>
  )
}
