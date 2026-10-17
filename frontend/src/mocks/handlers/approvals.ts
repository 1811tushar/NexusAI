import { http } from 'msw'
import type { ApprovalStatus } from '@/common/types/api'
import { actionLog, approvalScope, approvals, getRun, maybeResume } from '../runSimulator'
import { fail, ok, paged } from '../util'
import { currentUser } from './auth'

export const approvalHandlers = [
  http.get('/api/approvals/pending-count', () => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    return ok({ count: approvalScope(me.role, me.id).filter((a) => a.status === 'PENDING').length })
  }),
  http.get('/api/approvals', ({ request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const url = new URL(request.url); const status = url.searchParams.get('status') as ApprovalStatus | null
    return ok(paged(approvalScope(me.role, me.id).filter((a) => !status || a.status === status).sort((a, b) => b.requestedAt.localeCompare(a.requestedAt) || b.id - a.id), url))
  }),
  http.get('/api/approvals/:id', ({ params }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const a = approvalScope(me.role, me.id).find((x) => x.id === Number(params.id)); return a ? ok(a) : fail('NOT_FOUND', 'Approval not found.')
  }),
  http.post('/api/approvals/:id/decision', async ({ params, request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const a = approvals.find((x) => x.id === Number(params.id)); const run = a && getRun(a.investigationId)
    if (!a || !run) return fail('NOT_FOUND', 'Approval not found.')
    if (me.role === 'ANALYST') return fail('FORBIDDEN', 'Only approvers and administrators can decide approvals.')
    if (run.ownerId === me.id) return fail('SELF_APPROVAL_NOT_ALLOWED', 'You cannot approve actions from an investigation you started.')
    if (a.status !== 'PENDING') return fail('INVALID_STATE', 'This approval was already decided or has expired.')
    const b = (await request.json()) as { decision: 'APPROVE' | 'REJECT'; comment?: string }
    if (b.decision === 'REJECT' && !b.comment?.trim()) return fail('VALIDATION_FAILED', 'A reason is required when rejecting.', { comment: 'Explain why this is rejected.' })
    // Conditional update: only the first decision on a PENDING row wins (race safety).
    a.status = b.decision === 'APPROVE' ? 'APPROVED' : 'REJECTED'; a.decidedBy = { id: me.id, displayName: me.displayName }; a.decidedAt = new Date().toISOString(); a.comment = b.comment?.trim() || null
    maybeResume(run)
    return ok(a)
  }),
  http.get('/api/actions', ({ request }) => {
    const me = currentUser(); if (!me) return fail('UNAUTHENTICATED', 'Signed out.')
    const url = new URL(request.url)
    const rows = actionLog.filter((a) => me.role !== 'ANALYST' || getRun(a.investigationId)?.ownerId === me.id).sort((x, y) => y.executedAt.localeCompare(x.executedAt) || y.id - x.id)
    return ok(paged(rows, url))
  }),
]
