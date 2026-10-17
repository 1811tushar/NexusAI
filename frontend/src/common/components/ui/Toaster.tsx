import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { useToastStore } from './toastStore'
import { cn } from '@/common/utils/cn'

const tone = {
  success: { icon: CheckCircle2, cls: 'border-success' },
  error: { icon: AlertCircle, cls: 'border-danger' },
  info: { icon: Info, cls: 'border-info' },
}
export function Toaster() {
  const { toasts, dismiss, announcement } = useToastStore()
  return (
    <>
      <div role="status" aria-live="polite" className="sr-only">{announcement}</div>
      <div role="region" aria-label="Notifications" className="fixed bottom-20 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2 md:bottom-4">
        {toasts.map((t) => {
          const I = tone[t.tone].icon
          return (
            <div key={t.id} role={t.tone === 'error' ? 'alert' : 'status'} className={cn('flex items-start gap-3 rounded-md border bg-raised p-3 shadow-md', tone[t.tone].cls)}>
              <I className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div className="flex-1 text-sm"><p className="font-medium">{t.title}</p>{t.description && <p className="text-muted">{t.description}</p>}</div>
              <button aria-label="Dismiss notification" onClick={() => dismiss(t.id)} className="text-muted hover:text-ink"><X className="h-4 w-4" aria-hidden /></button>
            </div>
          )
        })}
      </div>
    </>
  )
}
