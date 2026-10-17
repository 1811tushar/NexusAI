import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, tokenStore } from './httpClient'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const ok = (data: unknown) => json(200, { success: true, data, error: null })
const session = { accessToken: 'new', expiresInSeconds: 900, user: {} }

describe('httpClient refresh', () => {
  beforeEach(() => tokenStore.set('old'))
  afterEach(() => vi.unstubAllGlobals())

  it('shares ONE refresh across concurrent 401s and retries each request once', async () => {
    let refreshCalls = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      if (url.endsWith('/auth/refresh')) { refreshCalls++; return ok(session) }
      const auth = (init.headers as Record<string, string>).Authorization
      return auth === 'Bearer new' ? ok({ fine: true }) : json(401, { success: false, data: null, error: { code: 'TOKEN_EXPIRED', message: 'x' } })
    }))
    const [a, b] = await Promise.all([http.get('/a'), http.get('/b')])
    expect(a).toEqual({ fine: true }); expect(b).toEqual({ fine: true })
    expect(refreshCalls).toBe(1)
  })

  it('normalises server errors into ApiError with code, details and requestId', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(400, { success: false, data: null, error: { code: 'VALIDATION_FAILED', message: 'Bad', details: { email: 'invalid' }, requestId: 'r1' } })))
    await expect(http.get('/x')).rejects.toMatchObject({ code: 'VALIDATION_FAILED', details: { email: 'invalid' }, requestId: 'r1' })
  })
})
