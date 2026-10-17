import type { ReactNode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AgentStepDTO } from './types'
import { useInvestigationRun } from './useInvestigationRun'
import { investigationApi } from './investigationApi'

type Msg = { id: number | null; event: string; data: unknown }
const h = vi.hoisted(() => ({ opts: null as null | { path: string | null; onMessage: (m: Msg) => void } }))
vi.mock('@/common/hooks/useSSE', () => ({ useSSE: (o: { path: string | null; onMessage: (m: Msg) => void }) => { h.opts = o } }))
vi.mock('./investigationApi', () => ({ investigationApi: { get: vi.fn(), steps: vi.fn(), streamPath: (id: number, after: number) => `/investigations/${id}/stream?after=${after}` } }))

const step = (seq: number, type: AgentStepDTO['type'], payload: object): AgentStepDTO => ({ seq, type, payload: payload as Record<string, unknown>, createdAt: '' })
const persisted = [
  step(1, 'run_started', { investigationId: 7, threadId: 't', startedAt: '' }),
  step(2, 'plan', { steps: [{ id: 's1', description: 'Compare', agent: 'DATA_ANALYST', status: 'PENDING' }] }),
  step(3, 'agent_started', { agent: 'DATA_ANALYST', stepId: 's1' }),
]
let client = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
const detail = (status: string) => ({ id: 7, status, approvals: [], question: 'Q' }) as never
const live = (id: number, event: string, data: object) => act(() => h.opts!.onMessage({ id, event, data }))

describe('useInvestigationRun', () => {
  beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); h.opts = null; vi.mocked(investigationApi.steps).mockResolvedValue(persisted) })

  it('rebuilds from persisted steps, then streams only what is newer (?after=lastSeq)', async () => {
    vi.mocked(investigationApi.get).mockResolvedValue(detail('RUNNING'))
    const { result } = renderHook(() => useInvestigationRun(7), { wrapper })
    await waitFor(() => expect(result.current.state.plan).toHaveLength(1))
    expect(result.current.state.lastSeq).toBe(3)
    await waitFor(() => expect(h.opts?.path).toBe('/investigations/7/stream?after=3'))
  })
  it('ignores replayed events it already has and applies new ones, including pause and completion', async () => {
    vi.mocked(investigationApi.get).mockResolvedValue(detail('RUNNING'))
    const { result } = renderHook(() => useInvestigationRun(7), { wrapper })
    await waitFor(() => expect(h.opts?.path).not.toBeNull())
    const before = result.current.state.timeline.length
    live(3, 'agent_started', { agent: 'DATA_ANALYST', stepId: 's1' })            // duplicate after reconnect
    live(2, 'plan', { steps: [] })                                               // older replay
    expect(result.current.state.timeline).toHaveLength(before); expect(result.current.state.plan).toHaveLength(1)
    live(4, 'approval_required', { actions: [{ actionKey: 'a', actionType: 'ADJUST_PRICE', risk: 'HIGH', title: 'A', description: '', params: {}, rationale: '', evidenceKeys: [] }] })
    expect(result.current.state.phase).toBe('AWAITING_APPROVAL')
    live(5, 'approval_decided', { approvalId: 1, actionKey: 'a', decision: 'APPROVE', decidedBy: 'R', comment: null })
    expect(result.current.state.phase).toBe('RUNNING')
    live(6, 'done', { status: 'COMPLETED', confidence: 0.8, loopsUsed: 1, usage: { inputTokens: 1, outputTokens: 1 }, latencyMs: 1 })
    expect(result.current.state.phase).toBe('COMPLETED')
    await waitFor(() => expect(h.opts?.path).toBeNull())                          // stream is closed after the terminal event
  })
  it('shows a failed run with its reason and does not open a stream for finished runs', async () => {
    vi.mocked(investigationApi.get).mockResolvedValue(detail('FAILED'))
    vi.mocked(investigationApi.steps).mockResolvedValue([...persisted, step(4, 'error', { code: 'LLM_RATE_LIMITED', message: 'slow', retryable: true })])
    const { result } = renderHook(() => useInvestigationRun(7), { wrapper })
    await waitFor(() => expect(result.current.state.phase).toBe('FAILED'))
    expect(result.current.state.error?.code).toBe('LLM_RATE_LIMITED'); expect(h.opts?.path).toBeNull()
  })
})
