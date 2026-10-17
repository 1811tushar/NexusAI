import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { ClaimStatusChip } from '@/common/components/ClaimStatusChip'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { ErrorState } from '@/common/components/ErrorState'
import { EvidenceCard } from '@/common/components/EvidenceCard'
import { PageHeader } from '@/common/components/PageHeader'
import { RiskBadge } from '@/common/components/RiskBadge'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { useAuthStore } from '@/features/auth/authStore'
import { formatParam, humanizeKey } from '@/features/investigations/labels'
import { investigationApi } from '@/features/investigations/investigationApi'
import { approvalApi } from './approvalApi'
import { DecisionDialog } from './DecisionDialog'
import { decisionBlockReason } from './decisionRules'

/** The complete chain behind one action: rationale, supporting claims, and every cited piece of evidence (FE-AP-04). */
export function ApprovalDetailPage() {
  const id = Number(useParams().id)
  const user = useAuthStore((s) => s.user)
  const [open, setOpen] = useState(false)
  const ap = useQuery({ queryKey: ['approvals', 'one', id], queryFn: () => approvalApi.get(id) })
  const inv = useQuery({ queryKey: ['investigation', ap.data?.investigationId], queryFn: () => investigationApi.get(ap.data!.investigationId), enabled: !!ap.data })
  if (ap.isPending) return <div className="space-y-3"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-48" /></div>
  if (ap.isError) return <ErrorState error={ap.error} onRetry={() => void ap.refetch()} />
  const a = ap.data
  const ownerId = inv.data?.owner.id
  const block = user ? decisionBlockReason({ role: user.role, userId: user.id, ownerId, status: a.status }) : null
  const evidence = (inv.data?.evidence ?? []).filter((e) => a.evidenceKeys.includes(e.evidenceKey))
  const claims = (inv.data?.claims ?? []).filter((c) => c.evidenceKeys.some((k) => a.evidenceKeys.includes(k)))
  return (
    <>
      <Link to="/approvals" className="mb-3 inline-flex items-center gap-1 text-sm text-accent underline"><ArrowLeft className="h-4 w-4" aria-hidden />All approvals</Link>
      <PageHeader title={a.title} description={a.description} actions={<div className="flex gap-2"><RiskBadge risk={a.risk} /><StatusBadge status={a.status} /></div>} />
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <Card><h2 className="mb-2 font-semibold">Why this action</h2><p className="text-sm">{a.rationale}</p><p className="mt-2 text-sm text-muted">From <Link className="text-accent underline" to={`/investigations/${a.investigationId}`}>{a.investigationQuestion}</Link></p></Card>
          <section aria-labelledby="claims-h"><h2 id="claims-h" className="mb-2 font-semibold">Claims behind it</h2>
            {inv.isPending ? <Skeleton className="h-20" /> : claims.length === 0 ? <p className="text-sm text-muted">No claims reference this evidence.</p> : <ul className="space-y-2">{claims.map((c) => <li key={c.id} className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface p-3 text-sm"><ClaimStatusChip status={c.status} /><span className="flex-1">{c.text}</span><span className="text-muted">{Math.round(c.confidence * 100)}%</span></li>)}</ul>}</section>
          <section aria-labelledby="ev-h"><h2 id="ev-h" className="mb-2 font-semibold">Evidence ({a.evidenceKeys.length})</h2>
            {inv.isPending ? <Skeleton className="h-32" /> : inv.isError ? <ErrorState error={inv.error} onRetry={() => void inv.refetch()} /> : evidence.length === 0 ? <p className="text-sm text-muted">No evidence is linked to this action.</p> : <ul className="space-y-3">{evidence.map((e) => <li key={e.evidenceKey}><EvidenceCard evidence={e} /></li>)}</ul>}</section>
        </div>
        <aside className="space-y-4">
          <Card className="space-y-2"><h2 className="font-semibold">Action details</h2>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">{Object.entries(a.params).map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{humanizeKey(k)}</dt><dd>{formatParam(k, v)}</dd></div>))}</dl>
            <ConfidenceGauge value={a.confidence} /></Card>
          <Card className="space-y-2"><h2 className="font-semibold">Decision</h2>
            {a.status === 'PENDING' ? (block ? <p className="text-sm">{block}</p> : <Button onClick={() => setOpen(true)}>Review and decide</Button>)
              : <p className="text-sm">{a.status === 'EXPIRED' ? 'This approval expired before anyone decided it. Nothing was executed.' : `${a.status === 'APPROVED' ? 'Approved' : 'Rejected'} by ${a.decidedBy?.displayName ?? 'an approver'}.`}{a.comment ? ` Comment: ${a.comment}` : ''}</p>}
            <p className="text-xs text-muted">Execution is simulated. No external system is changed.</p></Card>
        </aside>
      </div>
      {user && <DecisionDialog approval={a} role={user.role} userId={user.id} ownerId={ownerId} open={open} onOpenChange={setOpen} />}
    </>
  )
}
