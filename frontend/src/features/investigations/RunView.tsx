import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { ConfirmDialog } from '@/common/components/ConfirmDialog'
import { ErrorState } from '@/common/components/ErrorState'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/common/components/ui/Tabs'
import { toast } from '@/common/components/ui/toastStore'
import { isApiError } from '@/common/api/errors'
import { useAuthStore } from '@/features/auth/authStore'
import { AgentTimeline } from './AgentTimeline'
import { ApprovalPauseBanner } from './ApprovalPauseBanner'
import { EvidenceDrawer, EvidencePanel } from './EvidencePanel'
import { LoopNotice } from './LoopNotice'
import { PlanChecklist } from './PlanChecklist'
import { RunErrorCard } from './RunNotices'
import { investigationApi } from './investigationApi'
import { watchRun } from './runWatcher'
import { useInvestigationRun } from './useInvestigationRun'
import { useMediaQuery } from './useMediaQuery'

export function RunView({ id }: { id: number }) {
  const user = useAuthStore((s) => s.user)
  const nav = useNavigate()
  const { detail, state, loading, error } = useInvestigationRun(id)
  const wide = useMediaQuery('(min-width: 1024px)')
  const [open, setOpen] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)

  const cancel = useMutation({
    mutationFn: () => investigationApi.cancel(id),
    onSuccess: () => toast.info('Cancelling the investigation'),
    onError: (e) => toast.error('Could not cancel', isApiError(e) ? e.display : undefined),
  })
  const restart = useMutation({
    mutationFn: () => investigationApi.start({ question: detail.data?.question ?? '' }),
    onSuccess: (inv) => { watchRun(inv.id, inv.question); nav(`/investigations/${inv.id}`) },
    onError: (e) => toast.error('Could not start again', isApiError(e) ? e.display : undefined),
  })

  if (error) return <ErrorState error={error} onRetry={() => void detail.refetch()} />
  if (loading || !detail.data || !user) return <div className="space-y-3"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-64" /></div>
  const d = detail.data
  const active = state.phase === 'RUNNING' || state.phase === 'AWAITING_APPROVAL'
  const canCancel = active && (user.role === 'ADMIN' || (user.role === 'ANALYST' && d.owner.id === user.id))
  const opened = state.evidence.find((e) => e.evidenceKey === open) ?? null

  const plan = <Card><h2 className="mb-3 font-semibold">Plan</h2><PlanChecklist steps={state.plan} /></Card>
  const activity = <Card><h2 className="mb-3 font-semibold">Agent activity</h2><AgentTimeline items={state.timeline} toolResults={state.toolResults} /></Card>
  const side = (
    <div className="space-y-4">
      <Card className="space-y-3"><h2 className="font-semibold">Confidence</h2><ConfidenceGauge value={state.overall} threshold={state.threshold} />
        {state.confidenceHistory.length > 1 && <ol aria-label="Confidence by loop" className="space-y-1 text-xs text-muted">{state.confidenceHistory.map((c, i) => <li key={i}>Check {i + 1}: {Math.round(c.overall * 100)}%, {c.decision.toLowerCase().replace(/_/g, ' ')}</li>)}</ol>}</Card>
      <Card><h2 className="mb-3 font-semibold">Evidence ({state.evidence.length})</h2><EvidencePanel evidence={state.evidence} onOpen={setOpen} /></Card>
    </div>
  )

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1"><h1 className="text-xl font-semibold">{d.question}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted"><StatusBadge status={state.phase} />Started by {d.owner.displayName}{state.loop && <span>Loop {state.loop.current} of {state.loop.max}</span>}</p></div>
        {canCancel && <Button variant="secondary" onClick={() => setConfirmCancel(true)} loading={cancel.isPending}>Cancel investigation</Button>}
      </header>
      {state.phase === 'AWAITING_APPROVAL' && <ApprovalPauseBanner pending={state.pendingActions} approvals={d.approvals} role={user.role} userId={user.id} ownerId={d.owner.id} />}
      {state.phase === 'RUNNING' && state.loop && <LoopNotice loop={state.loop} />}
      {state.phase === 'FAILED' && <RunErrorCard code={state.error?.code} message={state.error?.message ?? 'The run failed.'} onRetry={() => restart.mutate()} retrying={restart.isPending} />}
      {wide ? <div className="grid grid-cols-[15rem_minmax(0,1fr)_20rem] items-start gap-4">{plan}{activity}{side}</div> : (
        <Tabs defaultValue="activity"><TabsList aria-label="Run sections"><TabsTrigger value="plan">Plan</TabsTrigger><TabsTrigger value="activity">Activity</TabsTrigger><TabsTrigger value="evidence">Evidence</TabsTrigger></TabsList>
          <TabsContent value="plan">{plan}</TabsContent><TabsContent value="activity">{activity}</TabsContent><TabsContent value="evidence">{side}</TabsContent></Tabs>)}
      <EvidenceDrawer evidence={opened} onClose={() => setOpen(null)} />
      <ConfirmDialog open={confirmCancel} onOpenChange={setConfirmCancel} danger title="Cancel this investigation?" confirmLabel="Cancel investigation"
        description="The run stops now. Anything already gathered stays in the trace. Pending approvals for this run will no longer be actionable." onConfirm={async () => { await cancel.mutateAsync() }} />
    </div>
  )
}
