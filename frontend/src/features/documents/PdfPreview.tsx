import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ErrorState } from '@/common/components/ErrorState'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { documentApi } from './documentApi'

/** Original PDF opened at the cited page using the browser's built-in viewer (no extra dependency). Loaded only when asked for (FE-DO-06).
 *  Needs `frame-src blob:` in the nginx CSP. */
export function PdfPreview({ docId, page }: { docId: number; page: number }) {
  const q = useQuery({ queryKey: ['documents', 'file', docId], queryFn: () => documentApi.file(docId), staleTime: Infinity })
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!q.data) return
    const u = URL.createObjectURL(new Blob([q.data], { type: 'application/pdf' })); setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [q.data])
  if (q.isPending) return <Skeleton className="h-96" />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />
  return url ? <iframe key={page} title={`Original PDF, page ${page}`} src={`${url}#page=${page}`} className="mb-4 h-[70vh] w-full rounded-lg border border-line bg-surface" /> : null
}
