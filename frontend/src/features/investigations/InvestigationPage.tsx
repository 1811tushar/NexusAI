import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { isApiError } from '@/common/api/errors'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { investigationApi } from './investigationApi'
import { ReportPage } from './ReportPage'
import { RunView } from './RunView'

/** One URL, two views: the live run while it is active, the report once it is terminal. */
export function InvestigationPage() {
  const id = Number(useParams().id)
  const d = useQuery({ queryKey: ['investigation', id], queryFn: () => investigationApi.get(id) })
  if (d.isPending) return <div className="space-y-3"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-64" /></div>
  if (d.isError) return isApiError(d.error) && d.error.code === 'NOT_FOUND'
    ? <EmptyState title="Investigation not found" hint="It may belong to someone else or no longer exist." />
    : <ErrorState error={d.error} onRetry={() => void d.refetch()} />
  return ['RUNNING', 'AWAITING_APPROVAL'].includes(d.data.status) ? <RunView key={id} id={id} /> : <ReportPage key={id} detail={d.data} />
}
