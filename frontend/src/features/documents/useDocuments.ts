import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { DocumentDTO, DocumentStatus } from '@/common/types/api'
import { toast } from '@/common/components/ui/toastStore'
import { isApiError } from '@/common/api/errors'
import { documentApi, type DocumentQuery } from './documentApi'

const IN_PROGRESS: DocumentStatus[] = ['UPLOADED', 'INGESTING', 'DELETING']
/** Polling is needed only while something is still being processed (FE-DO-02). */
export const hasInProgress = (docs?: DocumentDTO[]) => !!docs?.some((d) => IN_PROGRESS.includes(d.status))

export function useDocuments(params: DocumentQuery) {
  return useQuery({
    queryKey: ['documents', params],
    queryFn: () => documentApi.list(params),
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (hasInProgress(q.state.data?.items) ? 2000 : false),
  })
}

export function useDocumentActions() {
  const qc = useQueryClient()
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['documents'] }); void qc.invalidateQueries({ queryKey: ['dashboard'] }) }
  const msg = (e: unknown) => (isApiError(e) ? e.display : 'Something went wrong.')
  const remove = useMutation({
    mutationFn: (id: number) => documentApi.remove(id),
    onSuccess: () => { toast.success('Document deleted'); refresh() },
    onError: (e) => toast.error('Could not delete the document', msg(e)),
  })
  const reindex = useMutation({
    mutationFn: (id: number) => documentApi.reindex(id),
    onSuccess: () => { toast.info('Reindexing started'); refresh() },
    onError: (e) => toast.error('Could not reindex the document', msg(e)),
  })
  return { remove, reindex, refresh }
}
