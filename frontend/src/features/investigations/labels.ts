import type { ActionType, AgentName } from '@/common/types/api'
import type { ToolName } from './types'

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
export const agentLabel = (a: AgentName) => cap(a.toLowerCase().replace('_', ' '))
export const toolLabel: Record<ToolName, string> = {
  rag_search: 'Document search', sql_query: 'SQL query', web_search: 'Web search', stats_compare: 'Period comparison',
  stats_contribution: 'Contribution analysis', stats_anomaly: 'Anomaly check', recall_memory: 'Memory recall',
}
export const actionLabel: Record<ActionType, string> = {
  FLAG_FOR_REVIEW: 'Flag for review', CREATE_FOLLOWUP_TASK: 'Create follow-up task', SAVE_INSIGHT: 'Save insight',
  ADJUST_PRICE: 'Adjust price', PAUSE_CAMPAIGN: 'Pause campaign', REALLOCATE_BUDGET: 'Reallocate budget',
}
export const humanizeKey = (k: string) => cap(k.replace(/([A-Z])/g, ' $1').toLowerCase())
export function formatParam(key: string, v: unknown): string {
  if (typeof v === 'number') return /pct$/i.test(key) ? `${v > 0 ? '+' : ''}${v}%` : /amount|budget/i.test(key) ? v.toLocaleString() : String(v)
  if (/Id$/.test(key) && typeof v === 'number') return `#${v}`
  return String(v)
}
export const APPROVAL_TTL_DAYS = 7 // contract default; ApprovalDTO carries no expiresAt, so expiry is derived.
export function relativeTime(iso: string, now = Date.now()): string {
  const m = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
  if (m < 1) return 'just now'
  if (m < 60) return `${m} min ago`
  if (m < 1440) return `${Math.round(m / 60)} h ago`
  return `${Math.round(m / 1440)} d ago`
}
export function expiryText(requestedAt: string, now = Date.now()): string {
  const left = new Date(requestedAt).getTime() + APPROVAL_TTL_DAYS * 86_400_000 - now
  if (left <= 0) return 'Expired'
  const d = Math.floor(left / 86_400_000)
  return d >= 1 ? `Expires in ${d} d` : `Expires in ${Math.max(1, Math.round(left / 3_600_000))} h`
}
