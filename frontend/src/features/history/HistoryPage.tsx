import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { InvestigationStatus } from '@/common/types/api'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { PageHeader } from '@/common/components/PageHeader'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'
import { Input } from '@/common/components/ui/Input'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/common/components/ui/Table'
import { useDebounce } from '@/common/hooks/useDebounce'
import { formatDate, formatPct } from '@/common/utils/format'
import { useAuthStore } from '@/features/auth/authStore'
import { investigationApi } from '@/features/investigations/investigationApi'

const statuses: InvestigationStatus[] = ['RUNNING', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED', 'REFUSED']
const label = (s: string) => s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ')

export function HistoryPage() {
  const user = useAuthStore((s) => s.user); const nav = useNavigate()
  const [status, setStatus] = useState<InvestigationStatus | ''>(''); const [q, setQ] = useState(''); const [sort, setSort] = useState('createdAt,desc'); const [page, setPage] = useState(0)
  const dq = useDebounce(q.trim(), 300)
  const showOwner = user?.role !== 'ANALYST'
  const list = useQuery({
    queryKey: ['investigations', { status, dq, sort, page }], queryFn: () => investigationApi.list({ status, q: dq, sort, page, size: 10 }), placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items.some((i) => i.status === 'RUNNING' || i.status === 'AWAITING_APPROVAL') ? 5000 : false),
  })
  const filtered = !!(status || dq)
  const canAsk = user?.role !== 'APPROVER'
  return (
    <>
      <PageHeader title="History" description={showOwner ? 'Every investigation in the organisation.' : 'Your past investigations.'} />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1"><Input label="Search questions" value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} /></div>
        <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value as InvestigationStatus | ''); setPage(0) }} options={[{ value: '', label: 'All statuses' }, ...statuses.map((s) => ({ value: s, label: label(s) }))]} />
        <Select label="Sort by" value={sort} onChange={(e) => setSort(e.target.value)} options={[{ value: 'createdAt,desc', label: 'Newest' }, { value: 'createdAt,asc', label: 'Oldest' }, { value: 'confidence,desc', label: 'Highest confidence' }]} />
      </div>
      {list.isPending ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title={filtered ? 'No investigations match' : 'No investigations yet'} hint={filtered ? 'Clear the filters to see everything.' : 'Ask a question and the result will be kept here.'}
            action={filtered ? <Button variant="secondary" onClick={() => { setStatus(''); setQ('') }}>Clear filters</Button> : canAsk ? <Button onClick={() => nav('/investigate')}>Ask a question</Button> : undefined} />
        : (<>
          <Table aria-label="Investigations">
            <THead><TR><TH>Question</TH><TH>Status</TH><TH>Confidence</TH><TH>Loops</TH>{showOwner && <TH>Owner</TH>}<TH>Date</TH></TR></THead>
            <TBody>{list.data.items.map((i) => (
              <TR key={i.id}>
                <TD className="max-w-md"><Link className="font-medium text-accent underline" to={`/investigations/${i.id}`}>{i.question}</Link>{(i.status === 'RUNNING' || i.status === 'AWAITING_APPROVAL') && <span className="ml-2 text-xs text-muted">(live)</span>}</TD>
                <TD><StatusBadge status={i.status} /></TD><TD className="tabular-nums">{formatPct(i.confidence)}</TD><TD>{i.loopsUsed}</TD>{showOwner && <TD>{i.owner.displayName}</TD>}<TD className="whitespace-nowrap">{formatDate(i.createdAt)}</TD>
              </TR>))}</TBody></Table>
          <div className="mt-3 flex items-center justify-between text-sm"><span className="text-muted">Page {list.data.page + 1} of {list.data.totalPages}, {list.data.totalItems} investigations</span>
            <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="secondary" size="sm" disabled={page + 1 >= list.data.totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button></div></div>
        </>)}
    </>
  )
}
