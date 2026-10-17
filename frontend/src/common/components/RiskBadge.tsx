import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { Badge } from './ui/Badge'
import type { Risk } from '@/common/types/api'
export const RiskBadge = ({ risk }: { risk: Risk }) =>
  risk === 'HIGH'
    ? <Badge tone="danger" icon={<ShieldAlert className="h-3 w-3" />}>High risk</Badge>
    : <Badge tone="success" icon={<ShieldCheck className="h-3 w-3" />}>Low risk</Badge>
