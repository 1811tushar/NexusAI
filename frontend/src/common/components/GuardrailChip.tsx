import { ShieldAlert } from 'lucide-react'
import { Badge } from './ui/Badge'
import type { GuardrailAction, GuardrailCategory, GuardrailStage } from '@/common/types/api'
const words = (s: string) => s.toLowerCase().replace(/_/g, ' ')
/** Shows stage, action and category; the contract guarantees redacted values never arrive. */
export const GuardrailChip = ({ stage, action, category }: { stage: GuardrailStage; action: GuardrailAction; category: GuardrailCategory }) => (
  <Badge tone={action === 'BLOCKED' ? 'danger' : 'warning'} icon={<ShieldAlert className="h-3 w-3" />}>
    {`${words(stage)}: ${words(action)} (${words(category)})`}
  </Badge>
)
