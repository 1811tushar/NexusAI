import { useEffect, useRef, useState } from 'react'
import { ArrowDown } from 'lucide-react'
import { ClaimStatusChip } from '@/common/components/ClaimStatusChip'
import { GuardrailChip } from '@/common/components/GuardrailChip'
import { RiskBadge } from '@/common/components/RiskBadge'
import { Badge } from '@/common/components/ui/Badge'
import { Button } from '@/common/components/ui/Button'
import { formatPct } from '@/common/utils/format'
import { LoopNotice } from './LoopNotice'
import { actionLabel, agentLabel, toolLabel } from './labels'
import type { TimelineItem } from './runStore'
import type { ToolResultData } from './types'

function Entry({ item, result }: { item: TimelineItem; result?: ToolResultData }) {
  const e = item.event
  switch (e.type) {
    case 'run_started': return <p>Run started</p>
    case 'memory_recalled': return <p>Recalled {e.data.items.length} related past investigation{e.data.items.length === 1 ? '' : 's'}</p>
    case 'supervisor_routed': return <p><b>Supervisor</b> routed to {e.data.agents.map(agentLabel).join(' and ')}: {e.data.reason}</p>
    case 'plan': return <p>Plan ready with {e.data.steps.length} steps</p>
    case 'agent_started': return <p><b>{agentLabel(e.data.agent)}</b> started</p>
    case 'tool_call':
      return (
        <details>
          <summary className="cursor-pointer"><b>{agentLabel(e.data.agent)}</b> used {toolLabel[e.data.tool]}{result ? (result.ok ? `: ${result.summary}` : `: failed, ${result.summary}`) : ' (running)'}</summary>
          <pre className="mt-1 overflow-x-auto rounded-md bg-bg p-2 text-xs">{JSON.stringify(e.data.args, null, 2)}</pre>
          {result && <p className="mt-1 text-xs text-muted">{result.ok ? 'Succeeded' : 'Failed'} in {result.durationMs} ms</p>}
        </details>
      )
    case 'evidence_added': return <p>Evidence added: {e.data.evidence.title} <Badge tone="info">{e.data.evidence.kind.toLowerCase()}</Badge></p>
    case 'claims_drafted': return <p>{e.data.claims.length} claims drafted for verification</p>
    case 'claim_verified': return <p className="space-x-2"><ClaimStatusChip status={e.data.status} /><span>{e.data.text}</span><span className="text-muted">{formatPct(e.data.confidence)}</span></p>
    case 'confidence': return <p>Confidence check {formatPct(e.data.overall)} against {formatPct(e.data.threshold)}: {e.data.decision.toLowerCase().replace(/_/g, ' ')}</p>
    case 'loop': return <LoopNotice loop={{ current: e.data.loop, max: e.data.maxLoops, reason: e.data.reason, focus: e.data.focus }} />
    case 'action_proposed': return <p className="space-x-2"><span>Proposed {actionLabel[e.data.actionType]}: {e.data.title}</span><RiskBadge risk={e.data.risk} /></p>
    case 'approval_required': return <div><p className="font-medium">Approval required before anything is executed</p><ul className="mt-1 space-y-1">{e.data.actions.map((a) => <li key={a.actionKey} className="space-x-2"><span>{a.title}</span><RiskBadge risk={a.risk} /></li>)}</ul></div>
    case 'approval_decided': return <p>{e.data.decision === 'APPROVE' ? 'Approved' : 'Rejected'} by {e.data.decidedBy}{e.data.comment ? `: ${e.data.comment}` : ''}</p>
    case 'action_executed': return <p>{actionLabel[e.data.actionType]}: {e.data.status.toLowerCase()}. {e.data.note}</p>
    case 'guardrail_triggered': return <p className="space-x-2"><GuardrailChip stage={e.data.stage} action={e.data.action} category={e.data.category} /><span>{e.data.detail}</span></p>
    case 'report_ready': return <p>Report ready</p>
    case 'memory_saved': return <p>Saved a summary to memory</p>
    case 'error': return <p className="text-danger">Run failed: {e.data.message}</p>
    case 'done': return <p>Finished: {e.data.status.toLowerCase()}</p>
    default: return null
  }
}

interface Props { items: TimelineItem[]; toolResults: Record<string, ToolResultData>; autoScroll?: boolean }
/** Auto-scrolls to the newest entry; scrolling up pauses it and offers a way back (FE-IV-02). Focusable so keyboard users can scroll it. */
export function AgentTimeline({ items, toolResults, autoScroll = true }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [stick, setStick] = useState(true)
  useEffect(() => {
    const el = box.current
    if (autoScroll && stick && el) el.scrollTop = el.scrollHeight
  }, [items.length, autoScroll, stick])
  if (items.length === 0) return <p className="text-sm text-muted">No activity yet.</p>
  return (
    <div className="relative">
      <div ref={box} tabIndex={0} role="region" aria-label="Agent activity timeline"
        onScroll={(e) => { const el = e.currentTarget; setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 40) }}
        className="max-h-[32rem] overflow-y-auto pr-2">
        <ol className="space-y-3 border-l border-line pl-4 text-sm">
          {items.map((it, i) => (
            <li key={`${it.seq}-${i}`} className="relative"><span aria-hidden className="absolute -left-[1.3rem] top-1.5 h-2 w-2 rounded-full bg-accent" />
              <Entry item={it} result={it.event.type === 'tool_call' ? toolResults[it.event.data.callId] : undefined} /></li>
          ))}
        </ol>
      </div>
      {autoScroll && !stick && (
        <Button size="sm" variant="secondary" className="absolute bottom-2 right-4" onClick={() => setStick(true)}><ArrowDown className="h-4 w-4" aria-hidden />Jump to latest</Button>
      )}
    </div>
  )
}
