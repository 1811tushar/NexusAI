import { Link } from 'react-router-dom'
import { Clock } from 'lucide-react'
import { RiskBadge } from '@/common/components/RiskBadge'
import type { Role } from '@/common/types/api'
import type { ActionProposal, ApprovalDTO } from './types'

interface Props { pending: ActionProposal[]; approvals: ApprovalDTO[]; role: Role; userId: number; ownerId: number }
/** The run stays live; this resolves automatically once all approvals are decided. */
export function ApprovalPauseBanner({ pending, approvals, role, userId, ownerId }: Props) {
  const canDecide = role === 'APPROVER' || role === 'ADMIN'
  const isOwner = userId === ownerId
  return (
    <section role="status" aria-labelledby="pause-h" className="rounded-lg border border-warning bg-warning-soft p-4">
      <h2 id="pause-h" className="flex items-center gap-2 font-semibold"><Clock className="h-5 w-5 text-warning" aria-hidden />Waiting for approval</h2>
      <p className="mt-1 text-sm">High-impact actions need a human decision before anything is executed. Execution is simulated: no external system is changed. This page continues by itself once everything is decided.</p>
      <ul className="mt-3 space-y-2">
        {pending.map((a) => { const ap = approvals.find((x) => x.actionKey === a.actionKey); return (
          <li key={a.actionKey} className="flex flex-wrap items-center gap-2 text-sm"><span className="font-medium">{a.title}</span><RiskBadge risk={a.risk} />
            {canDecide && !isOwner && ap && <Link className="text-accent underline" to={`/approvals/${ap.id}`}>Review and decide</Link>}</li>) })}
      </ul>
      {!canDecide && <p className="mt-3 text-sm text-muted">Read-only for your role. An approver will decide.</p>}
      {canDecide && isOwner && <p className="mt-3 text-sm text-muted">You started this investigation, so another approver must decide.</p>}
    </section>
  )
}
