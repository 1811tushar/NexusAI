import { lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import { Brain, Database, ExternalLink, FileText, Globe, Sigma } from 'lucide-react'
import type { EvidenceKind } from '@/common/types/api'
import type { EvidenceDTO } from '@/common/types/evidence'
import { Badge } from './ui/Badge'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { DataTable } from './DataTable'

const EvidenceChart = lazy(() => import('./EvidenceChart'))
const kinds: Record<EvidenceKind, { icon: typeof FileText; label: string }> = {
  DOCUMENT: { icon: FileText, label: 'Document' }, SQL: { icon: Database, label: 'SQL' },
  STATS: { icon: Sigma, label: 'Statistics' }, WEB: { icon: Globe, label: 'Web' }, MEMORY: { icon: Brain, label: 'Memory' },
}
export function EvidenceCard({ evidence: e }: { evidence: EvidenceDTO }) {
  const K = kinds[e.kind]
  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold">{e.title}</h3>
        <Badge tone="info" icon={<K.icon className="h-3 w-3" />}>{K.label}</Badge>
      </div>
      <p className="text-sm text-muted">{e.snippet}</p>
      {e.source.sql && <pre className="overflow-x-auto rounded-md bg-bg p-2 text-xs"><code>{e.source.sql}</code></pre>}
      {e.data && <DataTable columns={e.data.columns} rows={e.data.rows} truncated={e.data.truncated} caption={e.title} />}
      {e.chart && <Suspense fallback={<Skeleton className="h-56 w-full" />}><EvidenceChart chart={e.chart} /></Suspense>}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {e.source.documentId !== undefined && (
          <Link className="text-accent underline" to={`/documents/${e.source.documentId}${e.source.chunkId !== undefined ? `?chunk=${e.source.chunkId}` : ''}`}>Open document{e.source.page ? `, page ${e.source.page}` : ''}</Link>
        )}
        {e.source.url && (
          <a className="inline-flex items-center gap-1 text-accent underline" href={e.source.url} target="_blank" rel="noopener noreferrer">
            Open source<ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        )}
        {e.score !== null && <span className="text-muted">Relevance {Math.round(e.score * 100)}%</span>}
      </div>
    </Card>
  )
}
