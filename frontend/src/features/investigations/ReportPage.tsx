import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Download, Printer } from 'lucide-react'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { EmptyState } from '@/common/components/EmptyState'
import { GuardrailChip } from '@/common/components/GuardrailChip'
import { MarkdownView } from '@/common/components/MarkdownView'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'
import { Card } from '@/common/components/ui/Card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/common/components/ui/Tabs'
import { toast } from '@/common/components/ui/toastStore'
import { isApiError } from '@/common/api/errors'
import { formatDate } from '@/common/utils/format'
import { useAuthStore } from '@/features/auth/authStore'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ClaimList } from './ClaimList'
import { EvidenceDrawer, EvidencePanel } from './EvidencePanel'
import { FeedbackBar } from './FeedbackBar'
import { RecommendationList } from './RecommendationList'
import { CancelledNote, RefusedCard, RunErrorCard } from './RunNotices'
import { TraceTab } from './TraceTab'
import { investigationApi } from './investigationApi'
import { watchRun } from './runWatcher'
import type { InvestigationDetailDTO } from './types'

const CONFIDENCE_MIN = 0.7 // contract default CONFIDENCE_MIN; the detail DTO does not carry the threshold
export const tocOf = (md: string) => Array.from(md.matchAll(/^(#{2,3})\s+(.+)$/gm)).map((m) => ({ level: m[1]!.length, text: m[2]!.trim() }))
const duration = (d: InvestigationDetailDTO) => d.usage ? `${(d.usage.latencyMs / 1000).toFixed(0)} s` : d.completedAt ? `${Math.max(1, Math.round((new Date(d.completedAt).getTime() - new Date(d.createdAt).getTime()) / 1000))} s` : 'n/a'

export function ReportPage({ detail: d }: { detail: InvestigationDetailDTO }) {
  const user = useAuthStore((s) => s.user)
  const nav = useNavigate()
  const [open, setOpen] = useState<string | null>(null)
  const md = useRef<HTMLDivElement>(null)
  const toc = useMemo(() => tocOf(d.reportMarkdown ?? ''), [d.reportMarkdown])
  const opened = d.evidence.find((e) => e.evidenceKey === open) ?? null
  const low = d.confidence !== null && d.confidence < CONFIDENCE_MIN
  const refused = d.status === 'REFUSED'

  const goTo = (text: string) => Array.from<Element>(md.current?.querySelectorAll('h2,h3') ?? []).find((h) => h.textContent?.trim() === text)?.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  const exportMd = useMutation({
    mutationFn: () => investigationApi.exportMarkdown(d.id),
    onSuccess: (blob) => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `investigation-${d.id}.md`; a.click(); URL.revokeObjectURL(a.href) },
    onError: (e) => toast.error('Export failed', isApiError(e) ? e.display : undefined),
  })
  const restart = useMutation({
    mutationFn: () => investigationApi.start({ question: d.question }),
    onSuccess: (inv) => { watchRun(inv.id, inv.question); nav(`/investigations/${inv.id}`) },
    onError: (e) => toast.error('Could not start again', isApiError(e) ? e.display : undefined),
  })

  return (
    <div className="space-y-5">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold">{d.question}</h1>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted">
          <StatusBadge status={d.status} /><span>{d.owner.displayName}</span><span>{formatDate(d.createdAt)}</span><span>Took {duration(d)}</span><span>{d.loopsUsed} {d.loopsUsed === 1 ? 'loop' : 'loops'}</span>
        </div>
        {!refused && <ConfidenceGauge value={d.confidence} threshold={CONFIDENCE_MIN} />}
        <div className="flex flex-wrap gap-2" data-no-print>
          <Button variant="secondary" size="sm" onClick={() => exportMd.mutate()} loading={exportMd.isPending} disabled={!d.reportMarkdown}><Download className="h-4 w-4" aria-hidden />Export Markdown</Button>
          <Button variant="secondary" size="sm" onClick={() => window.print()} disabled={!d.reportMarkdown}><Printer className="h-4 w-4" aria-hidden />Print or save as PDF</Button>
          <Button variant="ghost" size="sm" onClick={() => restart.mutate()} loading={restart.isPending} disabled={user?.role === 'APPROVER'}>Ask again</Button>
        </div>
      </header>
      {low && !refused && (
        <div role="alert" className="flex gap-2 rounded-md border border-warning bg-warning-soft p-3 text-sm"><AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden />
          <p><b>Low confidence.</b> Confidence is below the {Math.round(CONFIDENCE_MIN * 100)}% threshold. Treat these findings as leads to check, not as conclusions.</p></div>)}
      {refused && <RefusedCard guardrails={d.guardrailEvents} />}
      {d.status === 'FAILED' && <RunErrorCard message={d.errorMessage ?? 'The run failed.'} onRetry={user?.role === 'APPROVER' ? undefined : () => restart.mutate()} retrying={restart.isPending} />}
      {d.status === 'CANCELLED' && <CancelledNote />}

      <Tabs defaultValue={refused || !d.reportMarkdown ? 'trace' : 'report'}>
        <TabsList aria-label="Report sections" data-no-print>
          {d.reportMarkdown && <TabsTrigger value="report">Report</TabsTrigger>}
          {d.claims.length > 0 && <TabsTrigger value="claims">Claims ({d.claims.length})</TabsTrigger>}
          {d.evidence.length > 0 && <TabsTrigger value="evidence">Evidence ({d.evidence.length})</TabsTrigger>}
          <TabsTrigger value="trace">Trace</TabsTrigger>
        </TabsList>
        <TabsContent value="report" className="space-y-6">
          {d.summary && <Card><h2 className="mb-1 font-semibold">Executive summary</h2><p className="max-w-[var(--reading-width)] leading-7">{d.summary}</p></Card>}
          {d.limitations.length > 0 && (
            <section aria-labelledby="lim-h" className="rounded-lg border-2 border-warning bg-warning-soft p-4"><h2 id="lim-h" className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-5 w-5 text-warning" aria-hidden />Limitations and failures</h2>
              <p className="mt-1 text-sm">Some checks could not be completed. Nothing below was invented to fill the gap.</p><ul className="mt-2 list-disc space-y-1 pl-6 text-sm">{d.limitations.map((l) => <li key={l}>{l}</li>)}</ul></section>)}
          {d.guardrailEvents.length > 0 && (
            <section aria-labelledby="gr-h" className="rounded-lg border border-line bg-surface p-4"><h2 id="gr-h" className="font-semibold">Guardrails</h2>
              <ul className="mt-2 space-y-2 text-sm">{d.guardrailEvents.map((g, i) => <li key={i} className="flex flex-wrap items-center gap-2"><GuardrailChip stage={g.stage} action={g.action} category={g.category} /><span className="text-muted">{g.detail}</span></li>)}</ul></section>)}
          {toc.length > 2 && <nav aria-label="Table of contents" className="rounded-lg border border-line bg-surface p-3 text-sm" data-no-print><p className="mb-1 font-medium">On this page</p>
            <ul className="space-y-1">{toc.map((t, i) => <li key={i} style={{ paddingLeft: (t.level - 2) * 12 }}><button type="button" className="text-accent underline" onClick={() => goTo(t.text)}>{t.text}</button></li>)}</ul></nav>}
          <div ref={md}>{d.reportMarkdown && <MarkdownView>{d.reportMarkdown}</MarkdownView>}</div>
          <section aria-labelledby="rec-h"><h2 id="rec-h" className="mb-3 text-lg font-semibold">Recommendations</h2><RecommendationList recommendations={d.recommendations} approvals={d.approvals} actions={d.actions} />
            {d.approvals.length > 0 && <p className="mt-2 text-sm text-muted">Actions are simulated. No external system is changed. <Link className="text-accent underline" to="/approvals">See approvals</Link></p>}</section>
          {user?.id === d.owner.id && d.status === 'COMPLETED' && <FeedbackBar id={d.id} initial={d.feedbackRating} />}
        </TabsContent>
        <TabsContent value="claims"><ClaimList claims={d.claims} evidence={d.evidence} onOpenEvidence={setOpen} /></TabsContent>
        <TabsContent value="evidence">{d.evidence.length === 0 ? <EmptyState title="No evidence" /> : <EvidencePanel evidence={d.evidence} onOpen={setOpen} />}</TabsContent>
        <TabsContent value="trace"><TraceTab id={d.id} /></TabsContent>
      </Tabs>
      <EvidenceDrawer evidence={opened} onClose={() => setOpen(null)} />
    </div>
  )
}
