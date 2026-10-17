import type { ClaimStatus } from '@/common/types/api'
import type { EvidenceDTO } from '@/common/types/evidence'
import type {
  ActionProposal, AgentStepDTO, ConfidenceDecision, DoneData, GuardrailEvent, PlanStep, ReportReadyData, RunEvent, ToolResultData,
} from './types'

export type RunPhase = 'RUNNING' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REFUSED'
export const isTerminal = (p: RunPhase) => p === 'COMPLETED' || p === 'FAILED' || p === 'CANCELLED' || p === 'REFUSED'

export interface TimelineItem { seq: number; event: RunEvent }
export interface LiveClaim { claimKey: string; text: string; isKey: boolean; evidenceKeys: string[]; status: ClaimStatus | null; confidence: number | null; reason: string | null }
export interface ConfidencePoint { loop: number; overall: number; threshold: number; decision: ConfidenceDecision }
export interface RunState {
  lastSeq: number
  phase: RunPhase
  plan: PlanStep[]
  timeline: TimelineItem[]
  toolResults: Record<string, ToolResultData>
  evidence: EvidenceDTO[]
  claims: LiveClaim[]
  confidenceHistory: ConfidencePoint[]
  overall: number | null
  threshold: number
  loop: { current: number; max: number; reason: string; focus: string[] } | null
  pendingActions: ActionProposal[]
  decided: Extract<RunEvent, { type: 'approval_decided' }>['data'][]
  guardrails: GuardrailEvent[]
  reportDraft: string
  report: ReportReadyData | null
  error: Extract<RunEvent, { type: 'error' }>['data'] | null
  done: DoneData | null
}
export const initialRunState: RunState = {
  lastSeq: 0, phase: 'RUNNING', plan: [], timeline: [], toolResults: {}, evidence: [], claims: [], confidenceHistory: [], overall: null, threshold: 0.7,
  loop: null, pendingActions: [], decided: [], guardrails: [], reportDraft: '', report: null, error: null, done: null,
}

export type RunAction = { kind: 'hydrate'; steps: AgentStepDTO[] } | { kind: 'event'; seq: number | null; event: RunEvent }

/** Applies one event. Events with a seq at or below lastSeq are dropped: replay overlap after a reconnect never duplicates. */
export function applyEvent(state: RunState, seq: number | null, ev: RunEvent): RunState {
  if (seq !== null && seq <= state.lastSeq) return state
  const s: RunState = { ...state, lastSeq: seq ?? state.lastSeq }
  const withItem = (): RunState => ({ ...s, timeline: [...s.timeline, { seq: seq ?? s.lastSeq, event: ev }] })
  switch (ev.type) {
    case 'run_started': return { ...withItem(), phase: 'RUNNING' }
    case 'plan': return { ...withItem(), plan: ev.data.steps }
    case 'step_status': return { ...s, plan: s.plan.map((p) => (p.id === ev.data.stepId ? { ...p, status: ev.data.status } : p)) }
    case 'tool_result': return { ...s, toolResults: { ...s.toolResults, [ev.data.callId]: ev.data } }
    case 'report_delta': return { ...s, reportDraft: s.reportDraft + ev.data.text }
    case 'evidence_added': {
      const known = s.evidence.some((e) => e.evidenceKey === ev.data.evidence.evidenceKey)
      return { ...withItem(), evidence: known ? s.evidence : [...s.evidence, ev.data.evidence] }
    }
    case 'claims_drafted': {
      const merged = [...s.claims]
      ev.data.claims.forEach((c) => {
        const i = merged.findIndex((m) => m.claimKey === c.claimKey)
        const base = i >= 0 ? merged[i] : undefined
        const next: LiveClaim = { claimKey: c.claimKey, text: c.text, isKey: c.isKey, evidenceKeys: c.evidenceKeys, status: base?.status ?? null, confidence: base?.confidence ?? null, reason: base?.reason ?? null }
        if (i >= 0) merged[i] = next; else merged.push(next)
      })
      return { ...withItem(), claims: merged }
    }
    case 'claim_verified': {
      const d = ev.data
      const v: LiveClaim = { claimKey: d.claimKey, text: d.text, isKey: false, evidenceKeys: d.evidenceKeys, status: d.status, confidence: d.confidence, reason: d.reason }
      const i = s.claims.findIndex((c) => c.claimKey === d.claimKey)
      const claims = [...s.claims]
      if (i >= 0) claims[i] = { ...claims[i]!, ...v, isKey: claims[i]!.isKey }; else claims.push(v)
      return { ...withItem(), claims }
    }
    case 'confidence':
      return { ...withItem(), overall: ev.data.overall, threshold: ev.data.threshold, confidenceHistory: [...s.confidenceHistory, { loop: ev.data.loop, overall: ev.data.overall, threshold: ev.data.threshold, decision: ev.data.decision }] }
    case 'loop': return { ...withItem(), loop: { current: ev.data.loop, max: ev.data.maxLoops, reason: ev.data.reason, focus: ev.data.focus } }
    case 'approval_required': return { ...withItem(), phase: 'AWAITING_APPROVAL', pendingActions: ev.data.actions }
    case 'approval_decided': {
      const pendingActions = s.pendingActions.filter((a) => a.actionKey !== ev.data.actionKey)
      return { ...withItem(), pendingActions, decided: [...s.decided, ev.data], phase: pendingActions.length === 0 ? 'RUNNING' : s.phase }
    }
    case 'guardrail_triggered': return { ...withItem(), guardrails: [...s.guardrails, ev.data] }
    case 'report_ready': return { ...withItem(), report: ev.data, overall: ev.data.confidence }
    case 'error': return { ...withItem(), phase: 'FAILED', error: ev.data }
    case 'done': return { ...withItem(), phase: ev.data.status, done: ev.data }
    default: return withItem()
  }
}

export function runReducer(state: RunState, a: RunAction): RunState {
  if (a.kind === 'hydrate') return replay(a.steps)
  return applyEvent(state, a.seq, a.event)
}
/** Rebuilds the full live view from persisted steps (reload / reconnect / trace replay). */
export function replay(steps: AgentStepDTO[]): RunState {
  return [...steps].sort((x, y) => x.seq - y.seq).reduce((st, step) => applyEvent(st, step.seq, { type: step.type, data: step.payload } as unknown as RunEvent), initialRunState)
}
