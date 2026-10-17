import { CheckCircle2, HelpCircle, XOctagon } from 'lucide-react'
import { Badge } from './ui/Badge'
import type { ClaimStatus } from '@/common/types/api'
const m = {
  VERIFIED: { tone: 'success', label: 'Verified', icon: <CheckCircle2 className="h-3 w-3" /> },
  UNSUPPORTED: { tone: 'warning', label: 'Unsupported', icon: <HelpCircle className="h-3 w-3" /> },
  CONTRADICTED: { tone: 'danger', label: 'Contradicted', icon: <XOctagon className="h-3 w-3" /> },
} as const
export const ClaimStatusChip = ({ status }: { status: ClaimStatus }) => (
  <Badge tone={m[status].tone} icon={m[status].icon}>{m[status].label}</Badge>
)
