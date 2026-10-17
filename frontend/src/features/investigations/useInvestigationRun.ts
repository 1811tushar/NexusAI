import { useEffect, useReducer, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { announce } from '@/common/components/ui/toastStore'
import { useSSE } from '@/common/hooks/useSSE'
import { investigationApi } from './investigationApi'
import { initialRunState, isTerminal, runReducer } from './runStore'
import type { RunEvent } from './types'

const ACTIVE = ['RUNNING', 'AWAITING_APPROVAL']

/**
 * Live run: (1) load detail + persisted steps, (2) rebuild state from steps, (3) open the stream with ?after=lastSeq.
 * Reload, navigating away and back, or a dropped connection all end up here again; duplicates are impossible because the
 * reducer ignores any seq it already applied. The run itself lives on the server and never depends on this hook.
 */
export function useInvestigationRun(id: number) {
  const qc = useQueryClient()
  const detail = useQuery({ queryKey: ['investigation', id], queryFn: () => investigationApi.get(id) })
  const steps = useQuery({ queryKey: ['investigation', id, 'steps'], queryFn: () => investigationApi.steps(id), gcTime: 0, staleTime: 0 })
  const [state, dispatch] = useReducer(runReducer, initialRunState)
  const [path, setPath] = useState<string | null>(null)
  const hydrated = useRef(false)

  useEffect(() => {
    if (hydrated.current || !steps.data || !detail.data) return
    hydrated.current = true
    dispatch({ kind: 'hydrate', steps: steps.data })
    const last = steps.data.reduce((m, s) => Math.max(m, s.seq), 0)
    if (ACTIVE.includes(detail.data.status)) setPath(investigationApi.streamPath(id, last))
  }, [steps.data, detail.data, id])

  useSSE({
    path,
    onMessage: (m) => {
      const event = { type: m.event, data: m.data } as unknown as RunEvent
      dispatch({ kind: 'event', seq: m.id, event })
      // Polite live region: key milestones only (FE-A11-03).
      if (event.type === 'plan') announce(`Plan ready with ${event.data.steps.length} steps`)
      if (event.type === 'approval_required') announce(`Approval needed for ${event.data.actions.length} action${event.data.actions.length === 1 ? '' : 's'}`)
      if (event.type === 'done') announce(event.data.status === 'COMPLETED' ? 'Investigation completed' : `Investigation ${event.data.status.toLowerCase()}`)
      if (event.type === 'error') announce('Investigation failed')
    },
  })

  useEffect(() => {
    if (state.phase === 'AWAITING_APPROVAL') void qc.invalidateQueries({ queryKey: ['investigation', id] })
    if (isTerminal(state.phase) && hydrated.current) {
      setPath(null)
      void qc.invalidateQueries({ queryKey: ['investigation', id] })
      void qc.invalidateQueries({ queryKey: ['investigations'] })
      void qc.invalidateQueries({ queryKey: ['dashboard'] })
      void qc.invalidateQueries({ queryKey: ['approvals'] })
    }
  }, [state.phase, id, qc])

  return { detail, state, ready: hydrated.current, loading: detail.isPending || steps.isPending, error: detail.error ?? steps.error, connected: path !== null }
}
