import { AlertCircle } from 'lucide-react'
import { Button } from './ui/Button'
import { isApiError } from '@/common/api/errors'
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = isApiError(error) ? error.display : 'Something went wrong.'
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-danger bg-danger-soft p-4 text-danger">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="flex-1"><p className="font-medium">{msg}</p>
        {onRetry && <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>Try again</Button>}</div>
    </div>
  )
}
