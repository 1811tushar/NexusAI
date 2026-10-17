import { useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { http } from '@/common/api/httpClient'
import { isApiError } from '@/common/api/errors'
import type { MemoryDTO, PagedResponse } from '@/common/types/api'
import { PageHeader } from '@/common/components/PageHeader'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { ConfirmDialog } from '@/common/components/ConfirmDialog'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { IconButton } from '@/common/components/ui/IconButton'
import { Input } from '@/common/components/ui/Input'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { toast } from '@/common/components/ui/toastStore'
import { useDebounce } from '@/common/hooks/useDebounce'
import { formatDate } from '@/common/utils/format'

const memoryApi = {
  list: (q: string, page: number) => http.get<PagedResponse<MemoryDTO>>('/memories', { q, page, size: 10 }),
  remove: (id: number) => http.del<void>(`/memories/${id}`),
  clear: () => http.del<void>('/memories'),
}

export function MemoryPage() {
  const qc = useQueryClient()
  const [q, setQ] = useState(''); const [page, setPage] = useState(0)
  const [del, setDel] = useState<MemoryDTO | null>(null); const [forgetAll, setForgetAll] = useState(false)
  const dq = useDebounce(q.trim(), 300)
  const list = useQuery({ queryKey: ['memories', dq, page], queryFn: () => memoryApi.list(dq, page), placeholderData: keepPreviousData })
  const done = (t: string) => { toast.success(t); void qc.invalidateQueries({ queryKey: ['memories'] }) }
  const fail = (t: string) => (e: unknown) => toast.error(t, isApiError(e) ? e.display : undefined)
  const remove = useMutation({ mutationFn: memoryApi.remove, onSuccess: () => done('Memory deleted'), onError: fail('Could not delete the memory') })
  const clear = useMutation({ mutationFn: memoryApi.clear, onSuccess: () => done('Everything was forgotten'), onError: fail('Could not clear memory') })

  return (
    <>
      <PageHeader title="Memory" description="Short, factual summaries of your past investigations. They are private to you and help the agents avoid repeating work."
        actions={<Button variant="danger" disabled={!list.data?.totalItems} onClick={() => setForgetAll(true)}>Forget everything</Button>} />
      <div className="mb-4 max-w-md"><Input label="Search memory" value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} /></div>
      {list.isPending ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
        : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title={dq ? 'No memories match your search' : 'Nothing remembered yet'} hint={dq ? undefined : 'After an investigation completes, a short summary is saved here.'} />
        : (
          <>
            <ul className="space-y-3">{list.data.items.map((m) => (
              <li key={m.id}><Card className="flex items-start gap-3">
                <div className="flex-1 space-y-1"><p>{m.summary}</p>
                  <p className="text-xs text-muted">Saved {formatDate(m.createdAt)}{m.sourceInvestigationId !== null && <> from <Link className="text-accent underline" to={`/investigations/${m.sourceInvestigationId}`}>investigation {m.sourceInvestigationId}</Link></>}</p></div>
                <IconButton label="Delete this memory" onClick={() => setDel(m)}><Trash2 className="h-4 w-4" aria-hidden /></IconButton>
              </Card></li>))}</ul>
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-muted">Page {list.data.page + 1} of {list.data.totalPages}</span>
              <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="secondary" size="sm" disabled={page + 1 >= list.data.totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button></div>
            </div>
          </>
        )}
      <ConfirmDialog open={!!del} onOpenChange={(o) => !o && setDel(null)} danger title="Delete this memory?" confirmLabel="Delete memory"
        description="The agents will no longer use this summary. The investigation it came from is not affected." onConfirm={async () => { if (del) await remove.mutateAsync(del.id) }} />
      <ConfirmDialog open={forgetAll} onOpenChange={setForgetAll} danger typedConfirmation="FORGET" title="Forget everything?" confirmLabel="Forget everything"
        description="All saved summaries are permanently deleted. Your investigations and reports stay as they are." onConfirm={async () => { await clear.mutateAsync() }} />
    </>
  )
}
