import { http, HttpResponse } from 'msw'
import type { InvestigationStatus } from '@/common/types/api'
import type { AgentStepDTO } from '@/features/investigations/types'
import { allRuns, cancelRun, getRun, isTerm, startRun, toDTO, toDetail, type SimRun } from '../runSimulator'
import { fail, ok, paged } from '../util'
import { currentUser } from './auth'

type Me = NonNullable<ReturnType<typeof currentUser>>
const visible = (me: Me, r: SimRun | undefined) => (r && (me.role !== 'ANALYST' || r.ownerId === me.id) ? r : undefined)
const notFound = () => fail('NOT_FOUND', 'Investigation not found.')

export const investigationHandlers = [
  http.post('/api/investigations', async ({ request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    if (me.role === 'APPROVER') return fail('FORBIDDEN', 'Your role cannot start investigations.')
    const b = (await request.json()) as { question?: string; options?: { webSearch?: boolean; useMemory?: boolean; maxLoops?: number; documentIds?: number[] } }
    const q = (b.question ?? '').trim()
    if (q.length < 10 || q.length > 2000) return fail('VALIDATION_FAILED', 'Check the highlighted fields.', { question: 'Write between 10 and 2000 characters.' })
    if (allRuns().filter((r) => r.ownerId === me.id && r.status === 'RUNNING').length >= 2) return fail('RATE_LIMITED', 'You already have 2 investigations running. Wait for one to finish.')
    const run = startRun({ question: q, ownerId: me.id, ownerName: me.displayName, options: { webSearch: b.options?.webSearch ?? true, useMemory: b.options?.useMemory ?? true, maxLoops: Math.min(5, Math.max(1, b.options?.maxLoops ?? 3)), documentIds: b.options?.documentIds ?? null } })
    return ok(toDTO(run), 202)
  }),
  http.get('/api/investigations', ({ request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const url = new URL(request.url); const status = url.searchParams.get('status') as InvestigationStatus | null; const q = (url.searchParams.get('q') ?? '').toLowerCase()
    const mine = url.searchParams.get('mine') === 'true'; const [field = 'createdAt', dir = 'desc'] = (url.searchParams.get('sort') ?? 'createdAt,desc').split(',')
    const rows = allRuns().filter((r) => visible(me, r) && (!mine || r.ownerId === me.id) && (!status || r.status === status) && (!q || r.question.toLowerCase().includes(q))).map(toDTO)
    rows.sort((a, b2) => (field === 'confidence' ? (a.confidence ?? -1) - (b2.confidence ?? -1) : a.createdAt.localeCompare(b2.createdAt)) * (dir === 'asc' ? 1 : -1))
    return ok(paged(rows, url))
  }),
  http.get('/api/investigations/:id', ({ params }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); return r ? ok(toDetail(r)) : notFound()
  }),
  http.get('/api/investigations/:id/steps', ({ params }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); return r ? ok(r.steps) : notFound()
  }),
  // SSE: replay persisted events after `after` / Last-Event-ID, then tail live. Stays open (with heartbeat) while AWAITING_APPROVAL.
  http.get('/api/investigations/:id/stream', ({ params, request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); if (!r) return notFound()
    const url = new URL(request.url)
    const after = Math.max(Number(url.searchParams.get('after') ?? 0), Number(request.headers.get('Last-Event-ID') ?? 0))
    const enc = new TextEncoder(); let closed = false; let hb: number | undefined; let off: () => void = () => {}
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const close = () => { if (closed) return; closed = true; off(); clearInterval(hb); try { controller.close() } catch { /* already closed */ } }
        const send = (s: AgentStepDTO) => {
          if (closed) return
          controller.enqueue(enc.encode(`id: ${s.seq}\nevent: ${s.type}\ndata: ${JSON.stringify(s.payload)}\n\n`))
          if (s.type === 'done' || s.type === 'error') close()
        }
        r.steps.filter((s) => s.seq > after).forEach(send)
        if (closed) return
        if (isTerm(r.status)) return close()
        r.listeners.add(send); off = () => r.listeners.delete(send)
        hb = window.setInterval(() => { if (!closed) controller.enqueue(enc.encode(': ping\n\n')) }, 15000)
      },
      cancel() { closed = true; off(); clearInterval(hb) },
    })
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' } })
  }),
  http.post('/api/investigations/:id/cancel', ({ params }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); if (!r) return notFound()
    if (me.role === 'APPROVER' || (me.role === 'ANALYST' && r.ownerId !== me.id)) return fail('FORBIDDEN', 'You cannot cancel this investigation.')
    if (isTerm(r.status)) return fail('INVALID_STATE', 'This investigation has already finished.')
    cancelRun(r); return new Response(null, { status: 204 })
  }),
  http.post('/api/investigations/:id/feedback', async ({ params, request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); if (!r) return notFound()
    if (r.ownerId !== me.id) return fail('FORBIDDEN', 'Only the owner can leave feedback.')
    r.feedbackRating = ((await request.json()) as { rating: 1 | -1 }).rating; return ok(null)
  }),
  http.get('/api/investigations/:id/report.md', ({ params }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const r = visible(me, getRun(Number(params.id))); if (!r?.reportMarkdown) return notFound()
    const d = toDetail(r)
    const md = `# ${r.question}\n\n${d.reportMarkdown}\n\n## Claims\n\n${d.claims.map((c) => `- [${c.status}] ${c.text} (${Math.round(c.confidence * 100)}%)`).join('\n')}\n\n## Approvals\n\n${d.approvals.map((a) => `- ${a.title}: ${a.status}`).join('\n') || 'None'}\n\n_Actions are simulated; no external system was changed._\n`
    return new HttpResponse(md, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } })
  }),
]
