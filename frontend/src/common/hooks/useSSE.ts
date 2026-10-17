import { useEffect, useRef } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE, refreshSession, tokenStore } from '@/common/api/httpClient'

export interface SseMessage { id: number | null; event: string; data: unknown }
export interface UseSseOptions {
  /** Path under API_BASE, e.g. /investigations/12/stream. null disables the stream. */
  path: string | null
  method?: 'GET' | 'POST'
  body?: unknown
  onMessage: (m: SseMessage) => void
  onError?: (e: unknown) => void
  onClose?: () => void
}
class Fatal extends Error {}

/**
 * Authenticated SSE with Last-Event-ID resume, backoff reconnect and duplicate suppression:
 * events whose numeric id is <= the last delivered id are dropped (replay overlap after reconnect).
 */
export function useSSE(o: UseSseOptions) {
  const last = useRef<number>(-1)
  const cb = useRef(o)
  cb.current = o

  useEffect(() => {
    if (!o.path) return
    const ctrl = new AbortController()
    last.current = -1
    let attempts = 0
    void fetchEventSource(`${API_BASE}${o.path}`, {
      method: o.method ?? 'GET',
      body: o.body === undefined ? undefined : JSON.stringify(o.body),
      signal: ctrl.signal,
      credentials: 'include',
      openWhenHidden: true,
      // fetchEventSource re-sends these headers on reconnect, so Last-Event-ID is set by the library from the last event id it saw.
      headers: {
        ...(o.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(tokenStore.get() ? { Authorization: `Bearer ${tokenStore.get()}` } : {}),
      },
      async onopen(res) {
        if (res.status === 401 && (await refreshSession())) throw new Error('retry-after-refresh')
        if (res.status >= 400 && res.status < 500 && res.status !== 429) throw new Fatal(`HTTP ${res.status}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        attempts = 0
      },
      onmessage(ev) {
        const id = ev.id ? Number(ev.id) : null
        if (id !== null && id <= last.current) return
        if (id !== null) last.current = id
        let data: unknown = ev.data
        try { data = JSON.parse(ev.data) } catch { /* keep raw */ }
        cb.current.onMessage({ id, event: ev.event, data })
      },
      onclose() { cb.current.onClose?.() },
      onerror(err) {
        if (err instanceof Fatal) { cb.current.onError?.(err); throw err }
        attempts += 1
        if (attempts > 6) { cb.current.onError?.(err); throw err }
        return Math.min(1000 * 2 ** attempts, 15000)
      },
    }).catch(() => {})
    return () => ctrl.abort()
  }, [o.path, o.method]) // eslint-disable-line react-hooks/exhaustive-deps
}
