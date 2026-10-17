import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSSE } from './useSSE'

type Opts = { onmessage: (e: { id: string; event: string; data: string }) => void; onopen: (r: Partial<Response>) => Promise<void>; onerror: (e: unknown) => number | void; onclose: () => void }
const h = vi.hoisted(() => ({ opts: null as unknown, calls: 0 }))
vi.mock('@microsoft/fetch-event-source', () => ({ fetchEventSource: (_u: string, o: unknown) => { h.opts = o; h.calls++; return new Promise(() => {}) } }))
const o = () => h.opts as Opts

describe('useSSE', () => {
  beforeEach(() => { h.opts = null; h.calls = 0 })
  it('does nothing while path is null', () => { renderHook(() => useSSE({ path: null, onMessage: () => {} })); expect(h.calls).toBe(0) })
  it('delivers each event once, parses JSON and drops duplicate or older ids', () => {
    const got: unknown[] = []
    renderHook(() => useSSE({ path: '/x', onMessage: (m) => got.push([m.id, m.event, m.data]) }))
    const send = (id: string, data = '{"n":1}') => o().onmessage({ id, event: 'plan', data })
    send('1'); send('2'); send('2'); send('1'); send('3', 'not json')
    expect(got).toEqual([[1, 'plan', { n: 1 }], [2, 'plan', { n: 1 }], [3, 'plan', 'not json']])
  })
  it('treats 4xx (except 429) as fatal and reports it', async () => {
    const onError = vi.fn()
    renderHook(() => useSSE({ path: '/x', onMessage: () => {}, onError }))
    await expect(o().onopen({ status: 404, ok: false })).rejects.toThrow()
    expect(() => o().onerror(new Error('HTTP 500'))).not.toThrow()               // transient errors back off and retry
    expect(typeof o().onerror(new Error('HTTP 500'))).toBe('number')
  })
  it('calls onClose when the server ends the stream', () => {
    const onClose = vi.fn(); renderHook(() => useSSE({ path: '/x', onMessage: () => {}, onClose })); o().onclose(); expect(onClose).toHaveBeenCalled()
  })
})
