import { HttpResponse } from 'msw'
import type { ApiResponse, ErrorCode, PagedResponse, Role, UserDTO } from '@/common/types/api'

// One shared envelope type: handlers mix ok() and fail() in the same resolver, and msw infers a single response-body type per route.
type Envelope = ApiResponse<unknown>
export const ok = <T,>(data: T, status = 200): HttpResponse<Envelope> => HttpResponse.json<Envelope>({ success: true, data, error: null }, { status })
const statusFor: Partial<Record<ErrorCode, number>> = {
  VALIDATION_FAILED: 400, INVALID_CREDENTIALS: 401, UNAUTHENTICATED: 401, FORBIDDEN: 403, NOT_FOUND: 404, DUPLICATE_RESOURCE: 409,
  INVALID_STATE: 409, SELF_APPROVAL_NOT_ALLOWED: 403, RATE_LIMITED: 429, LLM_RATE_LIMITED: 503, AI_SERVICE_UNAVAILABLE: 503, FILE_TOO_LARGE: 413, UNSUPPORTED_FILE_TYPE: 415,
}
export const fail = (code: ErrorCode, message: string, details?: Record<string, string>): HttpResponse<Envelope> =>
  HttpResponse.json<Envelope>({ success: false, data: null, error: { code, message, details, requestId: crypto.randomUUID() } }, { status: statusFor[code] ?? 400 })

export function paged<T>(all: T[], url: URL): PagedResponse<T> {
  const page = Number(url.searchParams.get('page') ?? 0)
  const size = Math.min(100, Number(url.searchParams.get('size') ?? 20))
  return { items: all.slice(page * size, page * size + size), page, size, totalItems: all.length, totalPages: Math.max(1, Math.ceil(all.length / size)) }
}

// Current mock session survives reloads (sessionStorage) so silent restore works in dev and E2E.
const KEY = 'nx_mock_uid'
export const mockSession = {
  get: (): number | null => { const v = sessionStorage.getItem(KEY); return v ? Number(v) : null },
  set: (id: number | null) => (id === null ? sessionStorage.removeItem(KEY) : sessionStorage.setItem(KEY, String(id))),
}
export type MockUser = UserDTO & { password: string }
export const stripPassword = ({ password: _p, ...u }: MockUser): UserDTO => u
export const roleRank: Role[] = ['ANALYST', 'APPROVER', 'ADMIN']
