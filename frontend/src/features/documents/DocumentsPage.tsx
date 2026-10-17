import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import type { DocumentDTO, DocumentStatus, SourceType } from '@/common/types/api'
import { PageHeader } from '@/common/components/PageHeader'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { ConfirmDialog } from '@/common/components/ConfirmDialog'
import { Button } from '@/common/components/ui/Button'
import { IconButton } from '@/common/components/ui/IconButton'
import { Input } from '@/common/components/ui/Input'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/common/components/ui/Table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/common/components/ui/Tabs'
import { useDebounce } from '@/common/hooks/useDebounce'
import { formatBytes, formatDate } from '@/common/utils/format'
import { useAuthStore } from '@/features/auth/authStore'
import { IngestionStatus } from './IngestionStatus'
import { LibrarySearch } from './LibrarySearch'
import { UploadZone } from './UploadZone'
import { canManageDoc, canUpload } from './permissions'
import { useDocumentActions, useDocuments } from './useDocuments'

type Sort = 'new' | 'old' | 'title' | 'size'
const sorters: Record<Sort, (a: DocumentDTO, b: DocumentDTO) => number> = {
  new: (a, b) => b.createdAt.localeCompare(a.createdAt), old: (a, b) => a.createdAt.localeCompare(b.createdAt),
  title: (a, b) => a.title.localeCompare(b.title), size: (a, b) => b.sizeBytes - a.sizeBytes,
}

export function DocumentsPage() {
  const user = useAuthStore((s) => s.user)
  const [q, setQ] = useState(''); const [status, setStatus] = useState<DocumentStatus | ''>(''); const [type, setType] = useState<SourceType | ''>('')
  const [sort, setSort] = useState<Sort>('new'); const [page, setPage] = useState(0)
  const [toDelete, setToDelete] = useState<DocumentDTO | null>(null)
  const dq = useDebounce(q.trim(), 300)
  const list = useDocuments({ q: dq, status, sourceType: type, page, size: 10 })
  const { remove, reindex } = useDocumentActions()
  const items = useMemo(() => [...(list.data?.items ?? [])].sort(sorters[sort]), [list.data, sort])
  const filtered = !!(dq || status || type)
  const reset = (fn: () => void) => { fn(); setPage(0) }

  return (
    <>
      <PageHeader title="Documents" description="The shared company knowledge base the agents search and cite." />
      {canUpload(user?.role)
        ? <UploadZone onUploaded={() => void list.refetch()} />
        : <p className="rounded-md border border-line bg-surface p-3 text-sm text-muted">Your role can read and search documents. Ask an analyst or administrator to upload new ones.</p>}
      <Tabs defaultValue="library" className="mt-6">
        <TabsList aria-label="Documents views"><TabsTrigger value="library">Library</TabsTrigger><TabsTrigger value="search">Search inside documents</TabsTrigger></TabsList>
        <TabsContent value="library" className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1"><Input label="Search documents" value={q} onChange={(e) => reset(() => setQ(e.target.value))} placeholder="Title or file name" /></div>
            <Select label="Status" value={status} onChange={(e) => reset(() => setStatus(e.target.value as DocumentStatus | ''))}
              options={[{ value: '', label: 'All statuses' }, { value: 'READY', label: 'Ready' }, { value: 'INGESTING', label: 'Ingesting' }, { value: 'FAILED', label: 'Failed' }]} />
            <Select label="Type" value={type} onChange={(e) => reset(() => setType(e.target.value as SourceType | ''))}
              options={[{ value: '', label: 'All types' }, ...(['PDF', 'DOCX', 'TXT', 'MD'] as const).map((t) => ({ value: t, label: t }))]} />
            <Select label="Sort by" value={sort} onChange={(e) => setSort(e.target.value as Sort)}
              options={[{ value: 'new', label: 'Newest' }, { value: 'old', label: 'Oldest' }, { value: 'title', label: 'Title' }, { value: 'size', label: 'Largest' }]} />
          </div>
          {list.isPending ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
            : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
            : items.length === 0 ? (
              <EmptyState title={filtered ? 'No documents match your filters' : 'No documents yet'}
                hint={filtered ? 'Clear the filters to see everything.' : 'Upload a report or policy and the agents can start citing it.'}
                action={filtered ? <Button variant="secondary" onClick={() => { setQ(''); setStatus(''); setType(''); setPage(0) }}>Clear filters</Button> : undefined} />
            ) : (
              <>
                <Table aria-label="Documents">
                  <THead><TR><TH>Title</TH><TH>Type</TH><TH>Size</TH><TH>Status</TH><TH>Uploaded by</TH><TH>Date</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
                  <TBody>{items.map((d) => {
                    const manage = canManageDoc(user, d)
                    return (
                      <TR key={d.id}>
                        <TD><Link className="font-medium text-accent underline" to={`/documents/${d.id}`}>{d.title}</Link></TD>
                        <TD>{d.sourceType}</TD><TD>{formatBytes(d.sizeBytes)}</TD>
                        <TD><IngestionStatus doc={d} canManage={manage} onReindex={(id) => reindex.mutate(id)} reindexing={reindex.isPending && reindex.variables === d.id} /></TD>
                        <TD>{d.uploadedBy.displayName}</TD><TD className="whitespace-nowrap">{formatDate(d.createdAt)}</TD>
                        <TD>{manage && <IconButton label={`Delete ${d.title}`} onClick={() => setToDelete(d)}><Trash2 className="h-4 w-4" aria-hidden /></IconButton>}</TD>
                      </TR>
                    )
                  })}</TBody>
                </Table>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted">Page {(list.data?.page ?? 0) + 1} of {list.data?.totalPages ?? 1}, {list.data?.totalItems ?? 0} documents</span>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                    <Button variant="secondary" size="sm" disabled={page + 1 >= (list.data?.totalPages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next</Button>
                  </div>
                </div>
              </>
            )}
        </TabsContent>
        <TabsContent value="search"><LibrarySearch /></TabsContent>
      </Tabs>
      <ConfirmDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)} danger title="Delete this document?" confirmLabel="Delete document"
        description={<>“{toDelete?.title}” and its searchable passages will be removed. Past reports that cited it keep their saved evidence.</>}
        onConfirm={async () => { if (toDelete) await remove.mutateAsync(toDelete.id) }} />
    </>
  )
}
