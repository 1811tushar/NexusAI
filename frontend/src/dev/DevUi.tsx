import { useState, type ReactNode } from 'react'
import { ConfidenceGauge } from '@/common/components/ConfidenceGauge'
import { ConfirmDialog } from '@/common/components/ConfirmDialog'
import { CitationChip } from '@/common/components/CitationChip'
import { ClaimStatusChip } from '@/common/components/ClaimStatusChip'
import { DataTable } from '@/common/components/DataTable'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { EvidenceCard } from '@/common/components/EvidenceCard'
import { GuardrailChip } from '@/common/components/GuardrailChip'
import { MarkdownView } from '@/common/components/MarkdownView'
import { RiskBadge } from '@/common/components/RiskBadge'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Avatar } from '@/common/components/ui/Avatar'
import { Button } from '@/common/components/ui/Button'
import { Checkbox } from '@/common/components/ui/Checkbox'
import { Input } from '@/common/components/ui/Input'
import { Progress } from '@/common/components/ui/Progress'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Switch } from '@/common/components/ui/Switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/common/components/ui/Tabs'
import { Textarea } from '@/common/components/ui/Textarea'
import { toast } from '@/common/components/ui/toastStore'
import { Tooltip } from '@/common/components/ui/Tooltip'
import { useTheme } from '@/common/theme/ThemeProvider'
import type { ApprovalStatus, ClaimStatus, DocumentStatus, InvestigationStatus } from '@/common/types/api'

const S = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="space-y-3 border-b border-line pb-6"><h2 className="text-lg font-semibold">{title}</h2>{children}</section>)
const inv: InvestigationStatus[] = ['RUNNING', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED', 'REFUSED']
const docs: DocumentStatus[] = ['UPLOADED', 'INGESTING', 'READY', 'FAILED', 'DELETING']
const apr: ApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED', 'EXPIRED']

/** Dev-only gallery (route exists only when import.meta.env.DEV). Every primitive and domain component in its states. */
export function DevUi() {
  const { theme, setTheme } = useTheme()
  const [sw, setSw] = useState(true); const [confirm, setConfirm] = useState(false)
  return (
    <>
      <main className="mx-auto max-w-5xl space-y-6 p-6">
        <header className="flex items-center justify-between"><h1 className="text-2xl font-semibold">UI gallery</h1>
          <Button variant="secondary" onClick={() => setTheme(theme === 'DARK' ? 'LIGHT' : 'DARK')}>Theme: {theme}</Button></header>
        <S title="Buttons"><div className="flex flex-wrap gap-2"><Button>Primary</Button><Button variant="secondary">Secondary</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Danger</Button><Button loading>Saving</Button><Button disabled>Disabled</Button></div></S>
        <S title="Form controls"><div className="grid gap-3 md:grid-cols-2">
          <Input label="Default" placeholder="Type here" /><Input label="With error" defaultValue="bad" error="This value is not valid" />
          <Textarea label="Textarea" hint="A hint under the field" /><Select label="Select" options={[{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]} />
          <Checkbox label="Checkbox" defaultChecked /><div className="flex items-center gap-2"><Switch label="Switch" checked={sw} onCheckedChange={setSw} /><span className="text-sm">{sw ? 'On' : 'Off'}</span></div></div></S>
        <S title="Status, risk, claims, guardrails">
          <div className="flex flex-wrap gap-2">{[...inv, ...docs, ...apr].map((s, i) => <StatusBadge key={`${s}${i}`} status={s} />)}</div>
          <div className="flex flex-wrap gap-2"><RiskBadge risk="LOW" /><RiskBadge risk="HIGH" />{(['VERIFIED', 'UNSUPPORTED', 'CONTRADICTED'] as ClaimStatus[]).map((c) => <ClaimStatusChip key={c} status={c} />)}
            <GuardrailChip stage="INPUT" action="BLOCKED" category="PROMPT_INJECTION" /><GuardrailChip stage="OUTPUT" action="FLAGGED" category="INVALID_CITATION" /><GuardrailChip stage="TOOL" action="REDACTED" category="PII" /></div></S>
        <S title="Confidence gauge"><div className="grid gap-4 md:grid-cols-3"><ConfidenceGauge value={0.86} /><ConfidenceGauge value={0.52} /><ConfidenceGauge value={null} /></div></S>
        <S title="Feedback"><div className="grid gap-3 md:grid-cols-2"><Progress value={60} label="Demo progress" /><div className="flex gap-3"><Skeleton className="h-8 w-24" /><Avatar name="Ada Analyst" />
          <Tooltip label="A tooltip"><Button variant="secondary" size="sm">Hover or focus me</Button></Tooltip></div>
          <EmptyState title="Nothing here yet" hint="An empty state explains what to do next." action={<Button>Do it</Button>} /><ErrorState error={new Error('x')} onRetry={() => {}} /></div>
          <div className="flex gap-2"><Button variant="secondary" onClick={() => toast.success('Saved')}>Success toast</Button><Button variant="secondary" onClick={() => toast.error('Failed', 'Details here')}>Error toast</Button><Button variant="secondary" onClick={() => setConfirm(true)}>Confirm dialog</Button></div></S>
        <S title="Tabs"><Tabs defaultValue="a"><TabsList><TabsTrigger value="a">First</TabsTrigger><TabsTrigger value="b">Second</TabsTrigger></TabsList><TabsContent value="a">First panel</TabsContent><TabsContent value="b">Second panel</TabsContent></Tabs></S>
        <S title="Data and evidence">
          <DataTable columns={['Region', 'Q1', 'Q2']} rows={[['North', 120, 90], ['West', 80, 96]]} truncated />
          <p className="text-sm">Citations <CitationChip index={1} title="Q2 report" onClick={() => {}} /> <CitationChip index={2} title="Pricing policy" to="/documents/2" /></p>
          <EvidenceCard evidence={{ evidenceKey: 'e1', kind: 'SQL', title: 'Revenue by region', snippet: 'North fell 25 percent.', source: { sql: 'SELECT region, SUM(revenue) FROM sales GROUP BY 1' },
            data: { columns: ['Region', 'Revenue'], rows: [['North', 90], ['West', 96]], truncated: false }, chart: { type: 'bar', x: ['North', 'West'], series: [{ name: 'Revenue', values: [90, 96] }] }, score: 0.92, createdAt: '2026-01-01T00:00:00Z' }} /></S>
        <S title="Markdown (sanitised)"><MarkdownView>{'## Findings\n\nRevenue fell mainly in the **Northern** region.\n\n| Region | Change |\n|---|---|\n| North | -25% |\n\n[A link](https://example.com)\n\n<script>alert(1)</script>'}</MarkdownView></S>
        <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Confirm dialog" description="Focus is trapped here and returns to the trigger on close." confirmLabel="Confirm" onConfirm={() => {}} />
      </main>
    </>
  )
}
