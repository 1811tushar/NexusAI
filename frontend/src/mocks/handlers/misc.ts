import { http } from 'msw'
import type { DashboardSummaryDTO, InvestigationStatus } from '@/common/types/api'
import { advance, documents, memories } from '../db'
import { allRuns, toDTO } from '../runSimulator'
import { fail, ok, paged } from '../util'
import { currentUser } from './auth'

export const miscHandlers = [
  http.get('/api/memories', ({ request }) => {
    const url = new URL(request.url); const q = (url.searchParams.get('q') ?? '').toLowerCase()
    return ok(paged(memories.filter((m) => !q || m.summary.toLowerCase().includes(q)), url))
  }),
  http.delete('/api/memories/:id', ({ params }) => {
    const i = memories.findIndex((m) => m.id === Number(params.id)); if (i < 0) return fail('NOT_FOUND', 'Memory not found.')
    memories.splice(i, 1); return new Response(null, { status: 204 })
  }),
  http.delete('/api/memories', () => { memories.length = 0; return new Response(null, { status: 204 }) }),
  http.get('/api/dashboard/summary', () => {
    const u = currentUser(); if (!u) return fail('UNAUTHENTICATED', 'Signed out.')
    const visible = allRuns().map(toDTO).filter((i) => u.role !== 'ANALYST' || i.owner.id === u.id)
    const by: Record<InvestigationStatus, number> = { RUNNING: 0, AWAITING_APPROVAL: 0, COMPLETED: 0, FAILED: 0, CANCELLED: 0, REFUSED: 0 }
    visible.forEach((i) => { by[i.status] += 1 })
    const conf = visible.map((i) => i.confidence).filter((c): c is number => c !== null)
    const data: DashboardSummaryDTO = {
      investigationsByStatus: by, pendingApprovals: u.role === 'ANALYST' ? 0 : by.AWAITING_APPROVAL,
      documentsReady: documents.map(advance).filter((d) => d.status === 'READY').length,
      avgConfidence30d: conf.length ? conf.reduce((a, b) => a + b, 0) / conf.length : null, recent: visible.slice(0, 5),
    }
    return ok(data)
  }),
]
