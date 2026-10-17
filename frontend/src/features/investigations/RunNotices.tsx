import { Link } from 'react-router-dom'
import { AlertCircle, Ban, ShieldAlert } from 'lucide-react'
import { GuardrailChip } from '@/common/components/GuardrailChip'
import { Button } from '@/common/components/ui/Button'
import type { ErrorCode, GuardrailCategory } from '@/common/types/api'
import type { GuardrailEvent } from './types'

const rephrase: Record<GuardrailCategory, string> = {
  PROMPT_INJECTION: 'Ask the business question directly, without instructions about how the assistant should behave.',
  OFF_TOPIC: 'Focus the question on your company data, for example revenue, regions, products or marketing.',
  UNSAFE_REQUEST: 'Ask what you want to learn rather than asking the system to change or approve something.',
  PII: 'Remove personal details such as emails or phone numbers from the question.',
  INVALID_CITATION: 'Try the question again with a narrower scope.', INVALID_OUTPUT: 'Try the question again with a narrower scope.',
}
/** Calm refusal card: what happened, what did NOT happen, how to rephrase (ADD-GR-01). */
export function RefusedCard({ guardrails }: { guardrails: GuardrailEvent[] }) {
  const g = guardrails.find((x) => x.action === 'BLOCKED') ?? guardrails[0]
  return (
    <section aria-labelledby="refused-h" className="rounded-lg border border-warning bg-warning-soft p-5">
      <h2 id="refused-h" className="flex items-center gap-2 text-lg font-semibold"><ShieldAlert className="h-5 w-5 text-warning" aria-hidden />This question was not run</h2>
      <p className="mt-2 text-sm">The safety check stopped the request before any agent started.{g && <> Reason: <b>{g.category.toLowerCase().replace(/_/g, ' ')}</b>.</>}</p>
      <p className="mt-1 text-sm"><b>Nothing was executed:</b> no data was queried, no web search was made and no action was proposed.</p>
      {g && <p className="mt-1 text-sm"><b>How to rephrase:</b> {rephrase[g.category]}</p>}
      {g && <div className="mt-3"><GuardrailChip stage={g.stage} action={g.action} category={g.category} /></div>}
      <Link to="/investigate" className="mt-4 inline-block text-sm text-accent underline">Ask a different question</Link>
    </section>
  )
}

const errorHelp: Partial<Record<ErrorCode, string>> = {
  LLM_RATE_LIMITED: 'The AI provider is rate limiting requests. Wait about a minute and start again.',
  AI_SERVICE_UNAVAILABLE: 'The AI service is not responding right now. Try again in a few minutes.',
}
export function RunErrorCard({ code, message, onRetry, retrying }: { code?: ErrorCode; message: string; onRetry?: () => void; retrying?: boolean }) {
  return (
    <section role="alert" className="rounded-lg border border-danger bg-danger-soft p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-danger"><AlertCircle className="h-5 w-5" aria-hidden />The investigation could not finish</h2>
      <p className="mt-2 text-sm">{message}</p>
      {code && errorHelp[code] && <p className="mt-1 text-sm">{errorHelp[code]}</p>}
      <p className="mt-1 text-sm text-muted">Everything gathered before the failure is kept in the trace tab.</p>
      {onRetry && <Button className="mt-3" onClick={onRetry} loading={retrying}>Start again with the same question</Button>}
    </section>
  )
}
export const CancelledNote = () => (
  <p className="flex items-center gap-2 rounded-md border border-line bg-surface p-3 text-sm"><Ban className="h-4 w-4" aria-hidden />This investigation was cancelled. No actions were executed after the cancellation.</p>
)
