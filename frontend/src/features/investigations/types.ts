// Mirrors contract v2.1 sections 4.3 to 4.5 and 5. Change the contract first.
import type {
  ActionStatus, ActionType, AgentName, ApprovalStatus, ClaimStatus, ErrorCode, GuardrailAction, GuardrailCategory,
  GuardrailStage, InvestigationDTO, Risk,
} from '@/common/types/api'
import type { EvidenceDTO } from '@/common/types/evidence'

export type StepStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
export interface PlanStep { id: string; description: string; agent: AgentName; status: StepStatus }
export interface ClaimDTO { id: number; text: string; status: ClaimStatus; confidence: number; isKey: boolean; evidenceKeys: string[] }
export interface RecommendationDTO { id: string; text: string; risk: Risk; actionKey: string | null }
export interface ApprovalDTO {
  id: number; investigationId: number; investigationQuestion: string; actionKey: string; actionType: ActionType; title: string; description: string
  params: Record<string, unknown>; risk: Risk; rationale: string; evidenceKeys: string[]; confidence: number | null; status: ApprovalStatus
  requestedAt: string; decidedBy: { id: number; displayName: string } | null; decidedAt: string | null; comment: string | null
}
export interface ActionLogDTO {
  id: number; investigationId: number; approvalId: number | null; actionType: ActionType; params: Record<string, unknown>; risk: Risk
  status: ActionStatus; automatic: boolean; executedAt: string; note: string
}
export interface GuardrailEvent { stage: GuardrailStage; action: GuardrailAction; category: GuardrailCategory; detail: string }
export interface Usage { inputTokens: number; outputTokens: number; latencyMs: number }
export interface InvestigationDetailDTO extends InvestigationDTO {
  plan: PlanStep[]; reportMarkdown: string | null; limitations: string[]; guardrailEvents: GuardrailEvent[]; claims: ClaimDTO[]; evidence: EvidenceDTO[]
  recommendations: RecommendationDTO[]; approvals: ApprovalDTO[]; actions: ActionLogDTO[]; errorMessage: string | null; usage: Usage | null; feedbackRating: 1 | -1 | null
}
export interface StartInvestigationRequest {
  question: string
  options?: { webSearch?: boolean; documentIds?: number[]; useMemory?: boolean; maxLoops?: number }
}

export type ToolName = 'rag_search' | 'sql_query' | 'web_search' | 'stats_compare' | 'stats_contribution' | 'stats_anomaly' | 'recall_memory'
export interface ActionProposal {
  actionKey: string; actionType: ActionType; risk: Risk; title: string; description: string; params: Record<string, unknown>; rationale: string; evidenceKeys: string[]
}
export type ConfidenceDecision = 'ACCEPT' | 'LOOP' | 'ACCEPT_LOW_CONFIDENCE'
export interface ToolResultData { callId: string; tool: ToolName; ok: boolean; summary: string; durationMs: number }
export interface DoneData { status: 'COMPLETED' | 'CANCELLED' | 'REFUSED'; confidence: number | null; loopsUsed: number; usage: { inputTokens: number; outputTokens: number }; latencyMs: number }
export interface ReportReadyData { reportMarkdown: string; summary: string; recommendations: RecommendationDTO[]; confidence: number }

export type RunEvent =
  | { type: 'run_started'; data: { investigationId: number; threadId: string; startedAt: string } }
  | { type: 'memory_recalled'; data: { items: { id: number; summary: string; score: number }[] } }
  | { type: 'supervisor_routed'; data: { agents: AgentName[]; reason: string } }
  | { type: 'plan'; data: { steps: PlanStep[] } }
  | { type: 'step_status'; data: { stepId: string; status: Exclude<StepStatus, 'PENDING'> } }
  | { type: 'agent_started'; data: { agent: AgentName; stepId: string | null } }
  | { type: 'tool_call'; data: { callId: string; agent: AgentName; tool: ToolName; args: Record<string, unknown> } }
  | { type: 'tool_result'; data: ToolResultData }
  | { type: 'evidence_added'; data: { evidence: EvidenceDTO } }
  | { type: 'claims_drafted'; data: { claims: { claimKey: string; text: string; isKey: boolean; evidenceKeys: string[] }[] } }
  | { type: 'claim_verified'; data: { claimKey: string; text: string; status: ClaimStatus; confidence: number; evidenceKeys: string[]; reason: string } }
  | { type: 'confidence'; data: { overall: number; threshold: number; decision: ConfidenceDecision; loop: number } }
  | { type: 'loop'; data: { loop: number; maxLoops: number; reason: string; focus: string[] } }
  | { type: 'action_proposed'; data: ActionProposal }
  | { type: 'approval_required'; data: { actions: ActionProposal[] } }
  | { type: 'approval_decided'; data: { approvalId: number; actionKey: string; decision: 'APPROVE' | 'REJECT'; decidedBy: string; comment: string | null } }
  | { type: 'action_executed'; data: { actionLogId: number; actionKey: string; actionType: ActionType; status: ActionStatus; automatic: boolean; note: string } }
  | { type: 'guardrail_triggered'; data: GuardrailEvent }
  | { type: 'report_delta'; data: { text: string } }
  | { type: 'report_ready'; data: ReportReadyData }
  | { type: 'memory_saved'; data: { id: number; summary: string } }
  | { type: 'error'; data: { code: ErrorCode; message: string; retryable: boolean } }
  | { type: 'done'; data: DoneData }
export type AgentEventType = RunEvent['type']
/** Persisted trace row returned by GET /investigations/{id}/steps. */
export interface AgentStepDTO { seq: number; type: AgentEventType; payload: Record<string, unknown>; createdAt: string }
