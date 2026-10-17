import { WifiOff } from 'lucide-react'
import { useNetworkStatus } from '@/common/api/networkStatus'
export function NetworkBanner() {
  const unreachable = useNetworkStatus((s) => s.unreachable)
  if (!unreachable) return null
  return (
    <div role="alert" className="flex items-center gap-2 bg-danger-soft px-4 py-2 text-sm text-danger">
      <WifiOff className="h-4 w-4" aria-hidden />The server cannot be reached. Changes are not saved. We will keep retrying.
    </div>
  )
}
