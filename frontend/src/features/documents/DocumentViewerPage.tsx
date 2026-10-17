import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, FileText } from 'lucide-react'
import { PageHeader } from '@/common/components/PageHeader'
import { ErrorState } from '@/common/components/ErrorState'
import { EmptyState } from '@/common/components/EmptyState'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { toast } from '@/common/components/ui/toastStore'
import { cn } from '@/common/utils/cn'
import { formatBytes } from '@/common/utils/format'
import { documentApi } from './documentApi'
import { PdfPreview } from './PdfPreview'

/** Chunk list with page labels. `?chunk=ID` highlights and scrolls to the cited chunk (FE-DO-04). */
export function DocumentViewerPage() {
  const id = Number(useParams().id)
  const cited = Number(useSearchParams()[0].get('chunk') ?? NaN)
  const doc = useQuery({ queryKey: ['documents', 'one', id], queryFn: () => documentApi.get(id) })
  const chunks = useQuery({ queryKey: ['documents', 'chunks', id], queryFn: () => documentApi.chunks(id), enabled: doc.data?.status === 'READY' })

  const [showPdf, setShowPdf] = useState(false); const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    if (!chunks.data || Number.isNaN(cited)) return
    document.getElementById(`chunk-${cited}`)?.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  }, [chunks.data, cited])

  if (doc.isPending) return <Skeleton className="h-40" />
  if (doc.isError) return <ErrorState error={doc.error} onRetry={() => void doc.refetch()} />
  const d = doc.data
  const items = chunks.data?.items ?? []
  const pdfPage = items.find((c) => c.id === cited)?.page ?? items.find((c) => c.page !== null)?.page ?? 1
  const download = async () => {
    setDownloading(true)
    try { const a = document.createElement('a'); a.href = URL.createObjectURL(await documentApi.file(d.id)); a.download = d.originalFilename; a.click(); URL.revokeObjectURL(a.href) }
    catch { toast.error('Download failed', 'The original file could not be loaded.') } finally { setDownloading(false) }
  }
  return (
    <>
      <Link to="/documents" className="mb-3 inline-flex items-center gap-1 text-sm text-accent underline"><ArrowLeft className="h-4 w-4" aria-hidden />All documents</Link>
      <PageHeader title={d.title} description={`${d.sourceType}, ${formatBytes(d.sizeBytes)}${d.pageCount ? `, ${d.pageCount} pages` : ''}, uploaded by ${d.uploadedBy.displayName}`} actions={<StatusBadge status={d.status} />} />
      {d.status === 'READY' && (
        <div className="mb-4 flex flex-wrap gap-2">
          {d.sourceType === 'PDF' && <Button variant="secondary" size="sm" onClick={() => setShowPdf((v) => !v)}><FileText className="h-4 w-4" aria-hidden />{showPdf ? 'Hide original PDF' : `View original PDF at page ${pdfPage}`}</Button>}
          <Button variant="secondary" size="sm" onClick={() => void download()} loading={downloading}><Download className="h-4 w-4" aria-hidden />Download original</Button>
        </div>)}
      {showPdf && d.status === 'READY' && <PdfPreview docId={d.id} page={pdfPage} />}
      {d.status !== 'READY' ? <EmptyState title="This document is not searchable yet" hint={d.errorMessage ?? 'Passages appear here once ingestion finishes.'} />
        : chunks.isPending ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
        : chunks.isError ? <ErrorState error={chunks.error} onRetry={() => void chunks.refetch()} />
        : chunks.data.items.length === 0 ? <EmptyState title="No passages were extracted" />
        : <ol className="space-y-3">{chunks.data.items.map((c) => (
            <li key={c.id} id={`chunk-${c.id}`} aria-current={c.id === cited ? 'true' : undefined}
              className={cn('rounded-lg border bg-surface p-4', c.id === cited ? 'border-accent ring-2 ring-[var(--accent)]' : 'border-line')}>
              <p className="mb-1 text-xs text-muted">{c.page ? `Page ${c.page}` : 'No page'}{c.section ? `, ${c.section}` : ''}{c.id === cited ? ', cited passage' : ''}</p>
              <p className="max-w-[var(--reading-width)] leading-7">{c.content}</p>
            </li>))}</ol>}
    </>
  )
}
