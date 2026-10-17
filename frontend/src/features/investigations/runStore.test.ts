import { describe, expect, it } from 'vitest'
import { applyEvent, initialRunState, replay, type RunState } from './runStore'
import type { ActionProposal, AgentStepDTO, RunEvent } from './types'

const feed = (events: RunEvent[], from = 1, s: RunState = initialRunState) => events.reduce((st, e, i) => applyEvent(st, from + i, e), s)
const toSteps = (events: RunEvent[]): AgentStepDTO[] => events.map((e, i) => ({ seq: i + 1, type: e.type, payload: e.data as unknown as Record<string, unknown>, createdAt: '' }))
const plan: RunEvent = { type: 'plan', data: { steps: [{ id: 's1', description: 'Compare', agent: 'DATA_ANALYST', status: 'PENDING' }, { id: 's2', description: 'Verify', agent: 'ANALYST', status: 'PENDING' }] } }
const ev1 = { evidenceKey: 'e1', kind: 'SQL' as const, title: 'T', snippet: 's', source: {}, score: null, createdAt: '' }
const proposal = (k: string): ActionProposal => ({ actionKey: k, actionType: 'ADJUST_PRICE', risk: 'HIGH', title: k, description: '', params: {}, rationale: '', evidenceKeys: [] })
const done = (status: 'COMPLETED' | 'CANCELLED' | 'REFUSED' = 'COMPLETED'): RunEvent => ({ type: 'done', data: { status, confidence: 0.8, loopsUsed: 0, usage: { inputTokens: 1, outputTokens: 1 }, latencyMs: 1 } })

describe('runStore: normal run', () => {
  const s = feed([
    { type: 'run_started', data: { investigationId: 1, threadId: 't', startedAt: '' } }, plan,
    { type: 'step_status', data: { stepId: 's1', status: 'RUNNING' } }, { type: 'evidence_added', data: { evidence: ev1 } },
    { type: 'claims_drafted', data: { claims: [{ claimKey: 'c1', text: 'A', isKey: true, evidenceKeys: ['e1'] }] } },
    { type: 'claim_verified', data: { claimKey: 'c1', text: 'A', status: 'VERIFIED', confidence: 0.9, evidenceKeys: ['e1'], reason: '' } },
    { type: 'confidence', data: { overall: 0.9, threshold: 0.7, decision: 'ACCEPT', loop: 0 } }, done(),
  ])
  it('tracks plan status, evidence, claims, confidence and completion', () => {
    expect(s.plan.map((p) => p.status)).toEqual(['RUNNING', 'PENDING'])
    expect(s.evidence).toHaveLength(1)
    expect(s.claims[0]).toMatchObject({ status: 'VERIFIED', isKey: true, confidence: 0.9 })
    expect(s.overall).toBe(0.9); expect(s.phase).toBe('COMPLETED')
  })
})
describe('runStore: loop', () => {
  it('records the loop counter, reason and the confidence history', () => {
    const s = feed([{ type: 'confidence', data: { overall: 0.55, threshold: 0.7, decision: 'LOOP', loop: 0 } }, { type: 'loop', data: { loop: 1, maxLoops: 3, reason: 'low', focus: ['claim 3'] } },
      { type: 'confidence', data: { overall: 0.78, threshold: 0.7, decision: 'ACCEPT', loop: 1 } }])
    expect(s.loop).toEqual({ current: 1, max: 3, reason: 'low', focus: ['claim 3'] })
    expect(s.confidenceHistory.map((c) => c.decision)).toEqual(['LOOP', 'ACCEPT']); expect(s.overall).toBe(0.78)
  })
})
describe('runStore: approval pause and resume', () => {
  const paused = feed([{ type: 'approval_required', data: { actions: [proposal('a'), proposal('b')] } }])
  it('pauses with the pending actions', () => { expect(paused.phase).toBe('AWAITING_APPROVAL'); expect(paused.pendingActions).toHaveLength(2) })
  it('stays paused until every action is decided, then resumes and completes', () => {
    const one = applyEvent(paused, 2, { type: 'approval_decided', data: { approvalId: 1, actionKey: 'a', decision: 'APPROVE', decidedBy: 'R', comment: null } })
    expect(one.phase).toBe('AWAITING_APPROVAL'); expect(one.pendingActions.map((a) => a.actionKey)).toEqual(['b'])
    const two = applyEvent(one, 3, { type: 'approval_decided', data: { approvalId: 2, actionKey: 'b', decision: 'REJECT', decidedBy: 'R', comment: 'no' } })
    expect(two.phase).toBe('RUNNING'); expect(two.decided).toHaveLength(2)
    expect(applyEvent(two, 4, done()).phase).toBe('COMPLETED')
  })
})
describe('runStore: errors, refusal, cancel', () => {
  it('error ends FAILED and keeps the reason', () => {
    const s = feed([plan, { type: 'error', data: { code: 'LLM_RATE_LIMITED', message: 'slow down', retryable: true } }])
    expect(s.phase).toBe('FAILED'); expect(s.error).toMatchObject({ code: 'LLM_RATE_LIMITED', retryable: true }); expect(s.plan).toHaveLength(2)
  })
  it('a blocked input ends REFUSED with the guardrail event', () => {
    const s = feed([{ type: 'guardrail_triggered', data: { stage: 'INPUT', action: 'BLOCKED', category: 'PROMPT_INJECTION', detail: 'x' } }, done('REFUSED')])
    expect(s.phase).toBe('REFUSED'); expect(s.guardrails).toHaveLength(1)
  })
  it('cancel ends CANCELLED', () => { expect(feed([done('CANCELLED')]).phase).toBe('CANCELLED') })
})
describe('runStore: reconnect without duplicates', () => {
  const events: RunEvent[] = [plan, { type: 'evidence_added', data: { evidence: ev1 } }, { type: 'agent_started', data: { agent: 'ANALYST', stepId: null } }, { type: 'memory_saved', data: { id: 1, summary: 's' } }, done()]
  it('ignores events whose seq it already applied (server replay overlap)', () => {
    const first = feed(events.slice(0, 3))                      // seq 1..3 delivered before the drop
    const resumed = feed(events.slice(1), 2, first)              // server replays from seq 2 after reconnect
    expect(resumed.timeline).toHaveLength(events.length)         // no duplicates
    expect(resumed.evidence).toHaveLength(1); expect(resumed.lastSeq).toBe(5)
  })
  it('re-applying the same event returns the very same state object', () => {
    const s = feed(events); expect(applyEvent(s, 2, events[1]!)).toBe(s)
  })
  it('rebuilding from persisted steps equals the incrementally built state', () => { expect(replay(toSteps(events))).toEqual(feed(events)) })
  it('tool results attach by callId and streamed report text never enters the timeline', () => {
    const s = feed([{ type: 'tool_call', data: { callId: 'x', agent: 'DATA_ANALYST', tool: 'sql_query', args: {} } }, { type: 'tool_result', data: { callId: 'x', tool: 'sql_query', ok: false, summary: 'timeout', durationMs: 5 } }, { type: 'report_delta', data: { text: 'Hello' } }])
    expect(s.toolResults.x?.ok).toBe(false); expect(s.timeline).toHaveLength(1); expect(s.reportDraft).toBe('Hello')
  })
})
