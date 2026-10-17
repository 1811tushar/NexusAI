import { useState } from 'react'
import { Star } from 'lucide-react'
import type { ClaimStatus } from '@/common/types/api'
import { CitationChip } from '@/common/components/CitationChip'
import { ClaimStatusChip } from '@/common/components/ClaimStatusChip'
import { EmptyState } from '@/common/components/EmptyState'
import { Badge } from '@/common/components/ui/Badge'
import { cn } from '@/common/utils/cn'
import type { EvidenceDTO } from '@/common/types/evidence'
import type { ClaimDTO } from './types'

export type ClaimFilter = ClaimStatus | 'ALL'
export const filterClaims = (claims: ClaimDTO[], f: ClaimFilter) => (f === 'ALL' ? claims : claims.filter((c) => c.status === f))
const filters: { v: ClaimFilter; l: string }[] = [{ v: 'ALL', l: 'All' }, { v: 'VERIFIED', l: 'Verified' }, { v: 'UNSUPPORTED', l: 'Unsupported' }, { v: 'CONTRADICTED', l: 'Contradicted' }]

/** Unsupported and contradicted claims are always shown as such, never hidden or phrased as facts (A-4). */
export function ClaimList({ claims, evidence, onOpenEvidence }: { claims: ClaimDTO[]; evidence: EvidenceDTO[]; onOpenEvidence: (key: string) => void }) {
  const [f, setF] = useState<ClaimFilter>('ALL')
  const shown = filterClaims(claims, f)
  return (
    <div className="space-y-3">
      <div role="group" aria-label="Filter claims by status" className="flex flex-wrap gap-2">
        {filters.map(({ v, l }) => { const n = filterClaims(claims, v).length; return (
          <button key={v} type="button" aria-pressed={f === v} onClick={() => setF(v)}
            className={cn('rounded-md border px-3 py-1 text-sm', f === v ? 'border-accent bg-accent-soft font-medium text-accent' : 'border-line-strong bg-surface')}>{l} ({n})</button>) })}
      </div>
      {shown.length === 0 ? <EmptyState title="No claims in this view" hint="Choose another status filter." /> : (
        <ul className="space-y-3">{shown.map((c) => (
          <li key={c.id} className="rounded-lg border border-line bg-surface p-3">
            <p className="font-medium">{c.text}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <ClaimStatusChip status={c.status} /><span className="tabular-nums text-muted">Confidence {Math.round(c.confidence * 100)}%</span>
              {c.isKey && <Badge tone="accent" icon={<Star className="h-3 w-3" />}>Key claim</Badge>}
              <span className="ml-auto flex items-center gap-1">{c.evidenceKeys.length === 0 ? <span className="text-muted">No evidence cited</span> : c.evidenceKeys.map((k, i) => {
                const e = evidence.find((x) => x.evidenceKey === k); return <CitationChip key={k} index={i + 1} title={e?.title ?? 'Evidence'} onClick={() => onOpenEvidence(k)} /> })}</span>
            </div>
          </li>))}</ul>)}
    </div>
  )
}
