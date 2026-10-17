import type { EvalCategory, EvalRunDTO, EvalRunDetailDTO, EvalSystem } from './types'
export const SYSTEMS: EvalSystem[] = ['BASELINE', 'SINGLE_AGENT', 'AGENT_NO_VERIFIER', 'AGENT']
export const CATEGORIES: EvalCategory[] = ['NORMAL', 'EDGE', 'ADVERSARIAL', 'MISSING_DATA', 'TOOL_FAILURE']
export const systemLabel: Record<EvalSystem, string> = { BASELINE: 'Baseline RAG', SINGLE_AGENT: 'Single agent', AGENT_NO_VERIFIER: 'Agent without verifier', AGENT: 'Full NexusAI' }
/** Newest non-ablation run per system. Ablation runs carry a `variant` label. */
export function latestBySystem(runs: EvalRunDTO[]): Partial<Record<EvalSystem, EvalRunDTO>> {
  const out: Partial<Record<EvalSystem, EvalRunDTO>> = {}
  runs.filter((r) => r.variant === null).sort((a, b) => b.createdAt.localeCompare(a.createdAt)).forEach((r) => { out[r.system] ??= r })
  return out
}
export const ablationRuns = (runs: EvalRunDTO[]) => runs.filter((r) => r.variant !== null).sort((a, b) => (a.metrics.retrievalHitRate ?? 0) - (b.metrics.retrievalHitRate ?? 0))
/** Share of correct answers per category and system. */
export function categoryBreakdown(details: EvalRunDetailDTO[]) {
  return CATEGORIES.map((c) => ({ category: c, bySystem: Object.fromEntries(details.map((d) => { const r = d.results.filter((x) => x.category === c); return [d.system, r.length ? r.filter((x) => x.correct).length / r.length : null] })) as Partial<Record<EvalSystem, number | null>>, count: details[0]?.results.filter((x) => x.category === c).length ?? 0 }))
}
