import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type { SearchMode } from '@/common/types/api'
import { Input } from '@/common/components/ui/Input'
import { Select } from '@/common/components/ui/Select'
import { Skeleton } from '@/common/components/ui/Skeleton'
import { Card } from '@/common/components/ui/Card'
import { EmptyState } from '@/common/components/EmptyState'
import { ErrorState } from '@/common/components/ErrorState'
import { useDebounce } from '@/common/hooks/useDebounce'
import { highlight } from '@/common/utils/highlight'
import { documentApi } from './documentApi'

export function LibrarySearch() {
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<SearchMode>('HYBRID')
  const dq = useDebounce(q.trim(), 350)
  const res = useQuery({ queryKey: ['search', dq, mode], queryFn: () => documentApi.search(dq, mode), enabled: dq.length >= 2 })
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1"><Input label="Search inside documents" value={q} onChange={(e) => setQ(e.target.value)} placeholder="For example: supplier delay in the Northern region" /></div>
        <Select label="Search mode" value={mode} onChange={(e) => setMode(e.target.value as SearchMode)}
          options={[{ value: 'HYBRID', label: 'Hybrid (recommended)' }, { value: 'VECTOR', label: 'Meaning only' }, { value: 'KEYWORD', label: 'Keywords only' }]} />
      </div>
      {dq.length < 2 ? <EmptyState title="Search the knowledge base" hint="Type at least two characters. Results show the passage and where it came from." />
        : res.isPending ? <div className="space-y-2"><Skeleton className="h-20" /><Skeleton className="h-20" /></div>
        : res.isError ? <ErrorState error={res.error} onRetry={() => void res.refetch()} />
        : res.data.length === 0 ? <EmptyState title="No matching passages" hint="Try different words or switch the search mode." />
        : <ul className="space-y-3">{res.data.map((r) => (
            <li key={r.chunkId}><Card className="space-y-1">
              <Link className="font-semibold text-accent underline" to={`/documents/${r.documentId}?chunk=${r.chunkId}`}>{r.documentTitle}</Link>
              <p className="text-xs text-muted">{r.page ? `Page ${r.page}` : 'No page'}{r.section ? `, ${r.section}` : ''}, relevance {Math.round(r.score * 100)}%</p>
              <p className="text-sm">{highlight(r.snippet, dq)}</p>
            </Card></li>))}</ul>}
    </div>
  )
}
