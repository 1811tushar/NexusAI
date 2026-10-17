export type EvalSystem = 'BASELINE' | 'SINGLE_AGENT' | 'AGENT_NO_VERIFIER' | 'AGENT'
export type EvalCategory = 'NORMAL' | 'EDGE' | 'ADVERSARIAL' | 'MISSING_DATA' | 'TOOL_FAILURE'
export interface EvalMetrics {
  answerCorrectness: number; groundedClaimsShare: number; hallucinationRate: number; avgLatencyMs: number; avgTokens: number
  approvalGateCompliance: number | null; retrievalHitRate: number | null; citationValidity: number | null; guardrailBlockRate: number | null; failureRecoveryRate: number | null
}
export interface EvalRunDTO { id: number; createdAt: string; variant: string | null; system: EvalSystem; questionCount: number; metrics: EvalMetrics }
export interface EvalResult { questionId: string; category: EvalCategory; question: string; expectedFacts: string[]; answer: string; correct: boolean; groundedShare: number; hallucinated: boolean; latencyMs: number }
export interface EvalRunDetailDTO extends EvalRunDTO { results: EvalResult[] }
