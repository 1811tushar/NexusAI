import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { AgentTimeline } from './AgentTimeline'
import { investigationApi } from './investigationApi'
import { replay } from './runStore'

/** Read-only replay of the persisted trace. */
export function TraceTab({ id }: { id: number }) {
  const q = useQuery({ queryKey: ['investigation', id, 'trace'], queryFn: () => investigationApi.steps(id) })
  const state = useMemo(() => (q.data ? replay(q.data) : null), [q.data])
  if (q.isPending) return <Skeleton className="h-48" />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />
  if (!state || state.timeline.length === 0) return <EmptyState title="No trace recorded" hint="Nothing ran before this investigation ended." />
  return <AgentTimeline items={state.timeline} toolResults={state.toolResults} autoScroll={false} />
}
