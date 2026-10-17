import { useState } from 'react'
import type { ApprovalStatus } from '@/common/types/api'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { PageHeader } from '@/common/components/PageHeader'
import { Button } from '@/common/components/ui/Button'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/common/components/ui/Tabs'
import { useAuthStore } from '@/features/auth/authStore'
import { ApprovalCard } from './ApprovalCard'
import { useApprovals } from './useApprovals'

function Queue({ tab }: { tab: 'pending' | 'decided' }) {
  const [page, setPage] = useState(0); const [decided, setDecided] = useState<ApprovalStatus | ''>('')
  const status: ApprovalStatus | '' = tab === 'pending' ? 'PENDING' : decided
  const q = useApprovals(status, page)
  // "Decided" without a status filter also returns pending items, so those are removed client-side (paging counts can include them).
  const items = (q.data?.items ?? []).filter((a) => (tab === 'pending' ? a.status === 'PENDING' : a.status !== 'PENDING'))
  return (
    <div className="space-y-4">
      {tab === 'decided' && <Select label="Outcome" value={decided} onChange={(e) => { setDecided(e.target.value as ApprovalStatus | ''); setPage(0) }}
        options={[{ value: '', label: 'All decided' }, { value: 'APPROVED', label: 'Approved' }, { value: 'REJECTED', label: 'Rejected' }, { value: 'EXPIRED', label: 'Expired' }]} />}
      {q.isPending ? <div className="space-y-3"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
        : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        : items.length === 0 ? <EmptyState title={tab === 'pending' ? 'Nothing is waiting for approval' : 'No decided approvals yet'} hint={tab === 'pending' ? 'High-impact actions proposed by investigations appear here.' : 'Approved, rejected and expired actions are kept here.'} />
        : (<>
          <ul className="space-y-4">{items.map((a) => <li key={a.id}><ApprovalCard approval={a} /></li>)}</ul>
          <div className="flex items-center justify-between text-sm"><span className="text-muted">Page {(q.data?.page ?? 0) + 1} of {q.data?.totalPages ?? 1}</span>
            <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="secondary" size="sm" disabled={page + 1 >= (q.data?.totalPages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next</Button></div></div></>)}
    </div>
  )
}
export function ApprovalsPage() {
  const role = useAuthStore((s) => s.user?.role)
  return (
    <>
      <PageHeader title="Approvals" description={role === 'ANALYST' ? 'Approvals for your investigations. Approvers decide them.' : 'High-impact actions that need a human decision. Execution is simulated.'} />
      <Tabs defaultValue="pending"><TabsList aria-label="Approval lists"><TabsTrigger value="pending">Pending</TabsTrigger><TabsTrigger value="decided">Decided</TabsTrigger></TabsList>
        <TabsContent value="pending"><Queue tab="pending" /></TabsContent><TabsContent value="decided"><Queue tab="decided" /></TabsContent></Tabs>
    </>
  )
}
