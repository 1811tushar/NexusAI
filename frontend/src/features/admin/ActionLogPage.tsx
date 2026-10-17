import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { ActionStatus, ActionType } from '@/common/types/api'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { PageHeader } from '@/common/components/PageHeader'
import { RiskBadge } from '@/common/components/RiskBadge'
import { Badge, type Tone } from '@/common/components/ui/Badge'
import { Button } from '@/common/components/ui/Button'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/common/components/ui/Table'
import { formatDate } from '@/common/utils/format'
import { approvalApi } from '@/features/approvals/approvalApi'
import { actionLabel } from '@/features/investigations/labels'

const tone: Record<ActionStatus, Tone> = { EXECUTED: 'success', REJECTED: 'danger', EXPIRED: 'neutral', FAILED: 'danger' }
export function ActionLogPage() {
  const [page, setPage] = useState(0); const [status, setStatus] = useState<ActionStatus | ''>(''); const [type, setType] = useState<ActionType | ''>(''); const [mode, setMode] = useState('')
  const q = useQuery({ queryKey: ['actions', page], queryFn: () => approvalApi.actions(page, 20), placeholderData: keepPreviousData })
  // The contract's GET /actions defines paging only, so these filters apply to the loaded page.
  const items = useMemo(() => (q.data?.items ?? []).filter((a) => (!status || a.status === status) && (!type || a.actionType === type) && (!mode || (mode === 'auto' ? a.automatic : !a.automatic))), [q.data, status, type, mode])
  return (
    <>
      <PageHeader title="Action log" description="Every action that was executed, rejected, expired or failed. All executions are simulated." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value as ActionStatus | '')} options={[{ value: '', label: 'All statuses' }, ...(['EXECUTED', 'REJECTED', 'EXPIRED', 'FAILED'] as const).map((s) => ({ value: s, label: s.charAt(0) + s.slice(1).toLowerCase() }))]} />
        <Select label="Action" value={type} onChange={(e) => setType(e.target.value as ActionType | '')} options={[{ value: '', label: 'All actions' }, ...(Object.keys(actionLabel) as ActionType[]).map((t) => ({ value: t, label: actionLabel[t] }))]} />
        <Select label="How" value={mode} onChange={(e) => setMode(e.target.value)} options={[{ value: '', label: 'Automatic and approved' }, { value: 'auto', label: 'Automatic (low risk)' }, { value: 'approved', label: 'After approval' }]} />
      </div>
      {q.isPending ? <Skeleton className="h-64" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        : items.length === 0 ? <EmptyState title="No actions match" hint="Change the filters or check the next page." />
        : (<>
          <Table aria-label="Action log"><THead><TR><TH>When</TH><TH>Investigation</TH><TH>Action</TH><TH>Parameters</TH><TH>Risk</TH><TH>Status</TH><TH>How</TH><TH>Note</TH></TR></THead>
            <TBody>{items.map((a) => (<TR key={a.id}><TD className="whitespace-nowrap">{formatDate(a.executedAt)}</TD><TD><Link className="text-accent underline" to={`/investigations/${a.investigationId}`}>#{a.investigationId}</Link></TD>
              <TD>{actionLabel[a.actionType]}</TD><TD className="max-w-xs text-xs">{Object.entries(a.params).map(([k, v]) => `${k}: ${String(v)}`).join(', ')}</TD><TD><RiskBadge risk={a.risk} /></TD>
              <TD><Badge tone={tone[a.status]}>{a.status.charAt(0) + a.status.slice(1).toLowerCase()}</Badge></TD><TD>{a.automatic ? 'Automatic' : 'After approval'}</TD><TD className="max-w-xs text-xs text-muted">{a.note}</TD></TR>))}</TBody></Table>
          <div className="mt-3 flex items-center justify-between text-sm"><span className="text-muted">Page {(q.data?.page ?? 0) + 1} of {q.data?.totalPages ?? 1}</span>
            <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button><Button variant="secondary" size="sm" disabled={page + 1 >= (q.data?.totalPages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next</Button></div></div></>)}
    </>
  )
}
