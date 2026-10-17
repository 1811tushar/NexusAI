import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { InvestigationStatus } from '@/common/types/api'
import { PageHeader } from '@/common/components/PageHeader'
import { ErrorState } from '@/common/components/ErrorState'
import { EmptyState } from '@/common/components/EmptyState'
import { StatusBadge } from '@/common/components/StatusBadge'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Textarea } from '@/common/components/ui/Textarea'
import { formatDate } from '@/common/utils/format'
import { useAuthStore } from '@/features/auth/authStore'
import { useDashboard } from './useDashboard'

const order: InvestigationStatus[] = ['RUNNING', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED', 'REFUSED', 'CANCELLED']

export function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const nav = useNavigate()
  const [question, setQuestion] = useState('')
  const { data, isPending, isError, error, refetch } = useDashboard()
  const canAsk = user?.role === 'ADMIN' || user?.role === 'ANALYST'
  const showApprovals = user?.role === 'APPROVER' || user?.role === 'ADMIN'

  return (
    <>
      <PageHeader title={`Welcome, ${user?.displayName.split(' ')[0] ?? ''}`} description={user?.role === 'ANALYST' ? 'Your investigations and the shared knowledge base at a glance.' : 'Activity across the organisation at a glance.'} />
      {canAsk && (
        <Card className="mb-6">
          <form onSubmit={(e) => { e.preventDefault(); nav('/investigate', { state: { question: question.trim() } }) }} className="space-y-3">
            <Textarea label="Ask a business question" hint="Between 10 and 2000 characters. The agents plan, gather evidence and verify before answering." value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={2000} />
            <Button type="submit" disabled={question.trim().length < 10}>Start investigation</Button>
          </form>
        </Card>
      )}
      {isPending ? <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-32" /><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
        : isError ? <ErrorState error={error} onRetry={() => void refetch()} />
        : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <Card><h2 className="font-semibold">Investigations by status</h2>
                <ul className="mt-3 space-y-2 text-sm">{order.map((s) => (
                  <li key={s} className="flex items-center justify-between"><StatusBadge status={s} /><span className="tabular-nums">{data.investigationsByStatus[s] ?? 0}</span></li>))}</ul></Card>
              <Card className="space-y-3"><h2 className="font-semibold">Average confidence, last 30 days</h2>
                <ConfidenceGauge value={data.avgConfidence30d} />
                <p className="text-sm text-muted">Documents ready for search: <Link className="text-accent underline" to="/documents">{data.documentsReady}</Link></p></Card>
              {showApprovals && (
                <Card><h2 className="font-semibold">Pending approvals</h2>
                  <p className="mt-2 text-3xl font-semibold tabular-nums">{data.pendingApprovals}</p>
                  <Link className="mt-2 inline-block text-sm text-accent underline" to="/approvals">Review the queue</Link></Card>
              )}
            </div>
            <section className="mt-8" aria-labelledby="recent-h">
              <h2 id="recent-h" className="mb-3 text-lg font-semibold">Recent investigations</h2>
              {data.recent.length === 0
                ? <EmptyState title="No investigations yet" hint="Ask your first question to see the agents at work." action={canAsk ? <Button onClick={() => nav('/investigate')}>Ask a question</Button> : undefined} />
                : <ul className="divide-y divide-line rounded-lg border border-line bg-surface">{data.recent.map((i) => (
                    <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                      <div className="min-w-0 flex-1"><Link className="font-medium text-accent underline" to={`/investigations/${i.id}`}>{i.question}</Link>
                        <p className="text-xs text-muted">{i.owner.displayName}, {formatDate(i.createdAt)}</p></div>
                      <div className="flex items-center gap-3"><StatusBadge status={i.status} />{i.confidence !== null && <span className="text-sm tabular-nums">{Math.round(i.confidence * 100)}%</span>}</div>
                    </li>))}</ul>}
            </section>
          </>
        )}
    </>
  )
}
