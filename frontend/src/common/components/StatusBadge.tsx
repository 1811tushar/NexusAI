import type { ReactElement } from 'react'
import { Ban, CheckCircle2, CircleAlert, Clock, Loader2, ShieldAlert, XCircle } from 'lucide-react'
import { Badge, type Tone } from './ui/Badge'
import type { ApprovalStatus, DocumentStatus, InvestigationStatus } from '@/common/types/api'

type Status = InvestigationStatus | DocumentStatus | ApprovalStatus
const map: Record<Status, { tone: Tone; label: string; icon: ReactElement }> = {
  RUNNING: { tone: 'info', label: 'Running', icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  AWAITING_APPROVAL: { tone: 'warning', label: 'Awaiting approval', icon: <Clock className="h-3 w-3" /> },
  COMPLETED: { tone: 'success', label: 'Completed', icon: <CheckCircle2 className="h-3 w-3" /> },
  FAILED: { tone: 'danger', label: 'Failed', icon: <XCircle className="h-3 w-3" /> },
  CANCELLED: { tone: 'neutral', label: 'Cancelled', icon: <Ban className="h-3 w-3" /> },
  // REFUSED is distinct from FAILED: the input guardrail blocked the request and nothing ran.
  REFUSED: { tone: 'warning', label: 'Refused', icon: <ShieldAlert className="h-3 w-3" /> },
  UPLOADED: { tone: 'neutral', label: 'Uploaded', icon: <Clock className="h-3 w-3" /> },
  INGESTING: { tone: 'info', label: 'Ingesting', icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  READY: { tone: 'success', label: 'Ready', icon: <CheckCircle2 className="h-3 w-3" /> },
  DELETING: { tone: 'neutral', label: 'Deleting', icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  PENDING: { tone: 'warning', label: 'Pending', icon: <Clock className="h-3 w-3" /> },
  APPROVED: { tone: 'success', label: 'Approved', icon: <CheckCircle2 className="h-3 w-3" /> },
  REJECTED: { tone: 'danger', label: 'Rejected', icon: <XCircle className="h-3 w-3" /> },
  EXPIRED: { tone: 'neutral', label: 'Expired', icon: <CircleAlert className="h-3 w-3" /> },
}
export const StatusBadge = ({ status }: { status: Status }) => {
  const m = map[status]
  return <Badge tone={m.tone} icon={m.icon}>{m.label}</Badge>
}
