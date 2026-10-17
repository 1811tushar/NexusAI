import { lazy, Suspense, useMemo, useState, type ReactNode } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { PageHeader } from '@/common/components/PageHeader'
import { Badge } from '@/common/components/ui/Badge'
import { Card } from '@/common/components/ui/Card'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/common/components/ui/Table'
import { formatPct } from '@/common/utils/format'
import { cn } from '@/common/utils/cn'
import { evalApi } from './evalApi'
import { ablationRuns, categoryBreakdown, CATEGORIES, latestBySystem, SYSTEMS, systemLabel } from './evalMath'
import type { EvalCategory, EvalSystem } from './types'

const ComparisonChart = lazy(() => import('./EvalCharts').then((m) => ({ default: m.ComparisonChart })))
const TradeoffChart = lazy(() => import('./EvalCharts').then((m) => ({ default: m.TradeoffChart })))
const AblationChart = lazy(() => import('./EvalCharts').then((m) => ({ default: m.AblationChart })))
const Chart = ({ children }: { children: ReactNode }) => <Suspense fallback={<Skeleton className="h-72" />}>{children}</Suspense>
const catLabel = (c: string) => c.charAt(0) + c.slice(1).toLowerCase().replace('_', ' ')

export function EvalDashboard() {
  const runsQ = useQuery({ queryKey: ['eval', 'runs'], queryFn: evalApi.runs })
  const latest = useMemo(() => latestBySystem(runsQ.data ?? []), [runsQ.data])
  const ablation = useMemo(() => ablationRuns(runsQ.data ?? []), [runsQ.data])
  const detailQs = useQueries({ queries: SYSTEMS.flatMap((s) => (latest[s] ? [{ queryKey: ['eval', 'run', latest[s]!.id], queryFn: () => evalApi.run(latest[s]!.id) }] : [])) })
  const details = detailQs.flatMap((q) => (q.data ? [q.data] : []))
  const [sys, setSys] = useState<EvalSystem>('AGENT'); const [cat, setCat] = useState<EvalCategory | ''>(''); const [onlyBad, setOnlyBad] = useState(false); const [sel, setSel] = useState<string | null>(null)

  if (runsQ.isPending) return <div className="space-y-3"><Skeleton className="h-10 w-1/3" /><Skeleton className="h-64" /></div>
  if (runsQ.isError) return <ErrorState error={runsQ.error} onRetry={() => void runsQ.refetch()} />
  const present = SYSTEMS.filter((s) => latest[s])
  if (present.length === 0) return (<><PageHeader title="Evaluation" /><EmptyState title="No evaluation runs yet" hint="Run python -m app.evals.run_eval in the AI service. Results appear here." /></>)

  const rows = present.map((s) => ({ s, r: latest[s]! }))
  const cmp = rows.map(({ s, r }) => ({ system: systemLabel[s], correctness: r.metrics.answerCorrectness, grounded: r.metrics.groundedClaimsShare, hallucination: r.metrics.hallucinationRate }))
  const trade = rows.map(({ s, r }) => ({ system: systemLabel[s], tokens: r.metrics.avgTokens, correctness: r.metrics.answerCorrectness }))
  const agent = latest.AGENT; const breakdown = categoryBreakdown(details)
  const sysDetail = details.find((d) => d.system === sys)
  const results = (sysDetail?.results ?? []).filter((r) => (!cat || r.category === cat) && (!onlyBad || !r.correct || r.hallucinated))
  const picked = sysDetail?.results.find((r) => r.questionId === sel) ?? null
  const adversarial = sysDetail?.results.filter((r) => r.category === 'ADVERSARIAL') ?? []

  return (
    <>
      <PageHeader title="Evaluation" description="How the full agent compares with simpler systems on the same golden set. Measured values only." />
      <div className="space-y-8">
        <section aria-labelledby="cmp-h" className="space-y-3"><h2 id="cmp-h" className="text-lg font-semibold">System comparison</h2>
          <Table aria-label="System comparison"><THead><TR><TH>System</TH><TH>Correctness</TH><TH>Grounded claims</TH><TH>Hallucination</TH><TH>Citation validity</TH><TH>Latency</TH><TH>Avg tokens</TH><TH>Approval gate</TH></TR></THead>
            <TBody>{rows.map(({ s, r }) => (<TR key={s}><TD className="font-medium">{systemLabel[s]}</TD><TD>{formatPct(r.metrics.answerCorrectness)}</TD><TD>{formatPct(r.metrics.groundedClaimsShare)}</TD><TD>{formatPct(r.metrics.hallucinationRate)}</TD><TD>{formatPct(r.metrics.citationValidity)}</TD>
              <TD>{(r.metrics.avgLatencyMs / 1000).toFixed(1)} s</TD><TD>{r.metrics.avgTokens.toLocaleString()}</TD><TD>{r.metrics.approvalGateCompliance === null ? 'n/a' : <Badge tone={r.metrics.approvalGateCompliance === 1 ? 'success' : 'danger'}>{formatPct(r.metrics.approvalGateCompliance)}</Badge>}</TD></TR>))}</TBody></Table>
          <Chart><ComparisonChart data={cmp} /></Chart></section>
        <section aria-labelledby="trade-h" className="space-y-3"><h2 id="trade-h" className="text-lg font-semibold">Quality against token cost</h2>
          <p className="text-sm text-muted">Each point is a system. Further up is more correct; further right costs more tokens.</p><Chart><TradeoffChart data={trade} /></Chart></section>
        <section aria-labelledby="cat-h" className="space-y-3"><h2 id="cat-h" className="text-lg font-semibold">Correctness by question category</h2>
          {details.length === 0 ? <Skeleton className="h-40" /> : <Table aria-label="Correctness by category"><THead><TR><TH>Category</TH><TH>Questions</TH>{present.map((s) => <TH key={s}>{systemLabel[s]}</TH>)}</TR></THead>
            <TBody>{breakdown.map((b) => (<TR key={b.category}><TD className="font-medium">{catLabel(b.category)}</TD><TD>{b.count}</TD>{present.map((s) => <TD key={s}>{formatPct(b.bySystem[s] ?? null)}</TD>)}</TR>))}</TBody></Table>}</section>
        <section aria-labelledby="gr-h" className="space-y-3"><h2 id="gr-h" className="text-lg font-semibold">Guardrails and recovery (full agent)</h2>
          <div className="grid gap-3 sm:grid-cols-3">{[['Adversarial requests blocked', formatPct(agent?.metrics.guardrailBlockRate ?? null)], ['Faulted runs recovered honestly', formatPct(agent?.metrics.failureRecoveryRate ?? null)], ['Approval gate compliance', formatPct(agent?.metrics.approvalGateCompliance ?? null)]].map(([l, v]) => (<Card key={l}><p className="text-sm text-muted">{l}</p><p className="text-2xl font-semibold tabular-nums">{v}</p></Card>))}</div></section>
        <section aria-labelledby="abl-h" className="space-y-3"><h2 id="abl-h" className="text-lg font-semibold">Retrieval ablation</h2>
          {ablation.length === 0 ? <p className="text-sm text-muted">No retrieval ablation runs stored.</p> : (<>
            <Chart><AblationChart data={ablation.map((r) => ({ variant: r.variant ?? '', hit: r.metrics.retrievalHitRate ?? 0 }))} /></Chart>
            <Table aria-label="Retrieval ablation"><THead><TR><TH>Variant</TH><TH>Hit rate</TH><TH>Questions</TH></TR></THead><TBody>{[...ablation].reverse().map((r) => <TR key={r.id}><TD>{r.variant}</TD><TD>{formatPct(r.metrics.retrievalHitRate)}</TD><TD>{r.questionCount}</TD></TR>)}</TBody></Table></>)}</section>
        <section aria-labelledby="dd-h" className="space-y-3"><h2 id="dd-h" className="text-lg font-semibold">Question drill-down</h2>
          <div className="flex flex-wrap items-end gap-3"><Select label="System" value={sys} onChange={(e) => { setSys(e.target.value as EvalSystem); setSel(null) }} options={present.map((s) => ({ value: s, label: systemLabel[s] }))} />
            <Select label="Category" value={cat} onChange={(e) => setCat(e.target.value as EvalCategory | '')} options={[{ value: '', label: 'All categories' }, ...CATEGORIES.map((c) => ({ value: c, label: catLabel(c) }))]} />
            <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" className="accent-[var(--accent)]" checked={onlyBad} onChange={(e) => setOnlyBad(e.target.checked)} />Only failing or hallucinated</label></div>
          {adversarial.length > 0 && <p className="text-sm text-muted">{adversarial.filter((r) => r.correct).length} of {adversarial.length} adversarial questions were handled correctly by this system.</p>}
          {!sysDetail ? <Skeleton className="h-40" /> : results.length === 0 ? <EmptyState title="No questions match" /> : (
            <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
              <Table aria-label="Questions"><THead><TR><TH>Question</TH><TH>Category</TH><TH>Result</TH></TR></THead><TBody>{results.map((r) => (
                <TR key={r.questionId} className={cn(sel === r.questionId && 'bg-accent-soft')}><TD><button type="button" className="text-left text-accent underline" onClick={() => setSel(r.questionId)} aria-pressed={sel === r.questionId}>{r.question}</button></TD><TD>{catLabel(r.category)}</TD>
                  <TD>{r.hallucinated ? <Badge tone="danger">Hallucinated</Badge> : r.correct ? <Badge tone="success">Correct</Badge> : <Badge tone="warning">Incorrect</Badge>}</TD></TR>))}</TBody></Table>
              <Card aria-live="polite" className="space-y-2 self-start">{picked ? (<><h3 className="font-semibold">{picked.question}</h3>
                <div><p className="text-xs font-medium text-muted">Expected facts</p><ul className="list-disc pl-5 text-sm">{picked.expectedFacts.map((f) => <li key={f}>{f}</li>)}</ul></div>
                <div><p className="text-xs font-medium text-muted">Answer given</p><p className="text-sm">{picked.answer}</p></div>
                <p className="text-xs text-muted">Grounded claims {formatPct(picked.groundedShare)}, latency {(picked.latencyMs / 1000).toFixed(1)} s</p></>) : <p className="text-sm text-muted">Select a question to compare the answer with the expected facts.</p>}</Card>
            </div>)}</section>
      </div>
    </>
  )
}
