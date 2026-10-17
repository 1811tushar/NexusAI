import type { ApiResponse, AuthResponse, ErrorCode } from '@/common/types/api'
import { ApiError } from './errors'
import { useNetworkStatus } from './networkStatus'

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? '/api'

// Access token lives in memory only (FE-SH-04). Never localStorage.
let accessToken: string | null = null
let onSessionLost: () => void = () => {}
export const tokenStore = { get: () => accessToken, set: (t: string | null) => { accessToken = t } }
export const setSessionLostHandler = (fn: () => void) => { onSessionLost = fn }

let refreshing: Promise<AuthResponse | null> | null = null

/** One shared refresh for any number of concurrent 401s. */
export function refreshSession(): Promise<AuthResponse | null> {
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
      if (!res.ok) return null
      const body = (await res.json()) as ApiResponse<AuthResponse>
      if (!body.success || !body.data) return null
      accessToken = body.data.accessToken
      return body.data
    } catch {
      return null
    } finally {
      setTimeout(() => { refreshing = null }, 0)
    }
  })()
  return refreshing
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  signal?: AbortSignal
  skipAuth?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']) {
  const qs = new URLSearchParams()
  Object.entries(query ?? {}).forEach(([k, v]) => v !== undefined && v !== '' && qs.set(k, String(v)))
  const s = qs.toString()
  return `${API_BASE}${path}${s ? `?${s}` : ''}`
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const isForm = typeof FormData !== 'undefined' && opts.body instanceof FormData
  const headers: Record<string, string> = { 'X-Request-Id': crypto.randomUUID() }
  if (opts.body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (!opts.skipAuth && accessToken) headers.Authorization = `Bearer ${accessToken}`
  try {
    const res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? 'GET',
      headers,
      credentials: 'include',
      signal: opts.signal,
      body: opts.body === undefined ? undefined : isForm ? (opts.body as FormData) : JSON.stringify(opts.body),
    })
    useNetworkStatus.getState().setUnreachable(false)
    return res
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    useNetworkStatus.getState().setUnreachable(true)
    throw new ApiError('NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.', 0)
  }
}

async function toError(res: Response): Promise<ApiError> {
  let code: ErrorCode = 'INTERNAL_ERROR'
  let message = 'Something went wrong.'
  let details: Record<string, string> | undefined
  let requestId = res.headers.get('X-Request-Id') ?? undefined
  try {
    const body = (await res.json()) as ApiResponse<unknown>
    if (body.error) {
      code = body.error.code; message = body.error.message; details = body.error.details
      requestId = body.error.requestId ?? requestId
    }
  } catch { /* non-JSON error body */ }
  return new ApiError(code, message, res.status, details, requestId)
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res = await send(path, opts)
  if (res.status === 401 && !opts.skipAuth) {
    const session = await refreshSession()
    if (!session) { onSessionLost(); throw await toError(res) }
    res = await send(path, opts) // retry exactly once
    if (res.status === 401) { onSessionLost(); throw await toError(res) }
  }
  if (res.status === 204) return undefined as T
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as ApiResponse<T>
  if (!body.success) throw new ApiError(body.error?.code ?? 'INTERNAL_ERROR', body.error?.message ?? 'Request failed.', res.status, body.error?.details, body.error?.requestId)
  return body.data as T
}

export const http = {
  get: <T,>(p: string, query?: RequestOptions['query'], signal?: AbortSignal) => request<T>(p, { query, signal }),
  post: <T,>(p: string, body?: unknown, o: RequestOptions = {}) => request<T>(p, { ...o, method: 'POST', body }),
  patch: <T,>(p: string, body?: unknown) => request<T>(p, { method: 'PATCH', body }),
  del: <T,>(p: string) => request<T>(p, { method: 'DELETE' }),
}
