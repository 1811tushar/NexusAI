import { RefreshCw } from 'lucide-react'
import type { DocumentDTO } from '@/common/types/api'
import { StatusBadge } from '@/common/components/StatusBadge'
import { Button } from '@/common/components/ui/Button'

interface Props { doc: DocumentDTO; canManage: boolean; onReindex: (id: number) => void; reindexing?: boolean }
/** FAILED shows the stored reason and a Reindex action for people allowed to manage the document. */
export function IngestionStatus({ doc, canManage, onReindex, reindexing }: Props) {
  return (
    <div className="space-y-1">
      <StatusBadge status={doc.status} />
      {doc.status === 'FAILED' && (
        <div className="space-y-1">
          <p className="max-w-xs text-xs text-danger">{doc.errorMessage ?? 'Ingestion failed.'}</p>
          {canManage && (
            <Button size="sm" variant="secondary" loading={reindexing} onClick={() => onReindex(doc.id)}>
              <RefreshCw className="h-3 w-3" aria-hidden />Reindex
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
