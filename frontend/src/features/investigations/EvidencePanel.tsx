import { Brain, Database, FileText, Globe, Sigma } from 'lucide-react'
import { Dialog, DialogContent } from '@/common/components/ui/Dialog'
import { EvidenceCard } from '@/common/components/EvidenceCard'
import type { EvidenceKind } from '@/common/types/api'
import type { EvidenceDTO } from '@/common/types/evidence'

const icons: Record<EvidenceKind, typeof FileText> = { DOCUMENT: FileText, SQL: Database, STATS: Sigma, WEB: Globe, MEMORY: Brain }
export function EvidencePanel({ evidence, onOpen }: { evidence: EvidenceDTO[]; onOpen: (key: string) => void }) {
  if (evidence.length === 0) return <p className="text-sm text-muted">Evidence appears here as the agents find it.</p>
  return (
    <ul aria-label="Evidence collected" className="space-y-2">
      {evidence.map((e) => { const I = icons[e.kind]; return (
        <li key={e.evidenceKey}>
          <button type="button" onClick={() => onOpen(e.evidenceKey)} className="w-full rounded-md border border-line bg-surface p-2 text-left hover:bg-accent-soft">
            <span className="flex items-center gap-2 text-sm font-medium"><I className="h-4 w-4 shrink-0 text-accent" aria-hidden />{e.title}</span>
            <span className="mt-1 line-clamp-2 block text-xs text-muted">{e.snippet}</span>
          </button>
        </li>) })}
    </ul>
  )
}
/** Side drawer with the full evidence card. Radix traps focus, Esc closes, focus returns to the opener. */
export function EvidenceDrawer({ evidence, onClose }: { evidence: EvidenceDTO | null; onClose: () => void }) {
  return (
    <Dialog open={!!evidence} onOpenChange={(o) => !o && onClose()}>
      {evidence && <DialogContent side="right" title="Evidence details" description="Where this evidence came from and what it shows."><EvidenceCard evidence={evidence} /></DialogContent>}
    </Dialog>
  )
}
