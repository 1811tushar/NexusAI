import { forwardRef, useId, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/common/utils/cn'
interface Props extends TextareaHTMLAttributes<HTMLTextAreaElement> { label: string; error?: string; hint?: string }
export const Textarea = forwardRef<HTMLTextAreaElement, Props>(({ label, error, hint, className, id, ...p }, ref) => {
  const auto = useId(); const iid = id ?? auto
  return (
    <div className="space-y-1">
      <label htmlFor={iid} className="block text-sm font-medium">{label}</label>
      <textarea ref={ref} id={iid} aria-invalid={!!error} aria-describedby={error ? `${iid}-err` : hint ? `${iid}-hint` : undefined}
        className={cn('min-h-24 w-full rounded-md border bg-surface px-3 py-2 text-ink placeholder:text-muted', error ? 'border-danger' : 'border-line-strong', className)} {...p} />
      {hint && !error && <p id={`${iid}-hint`} className="text-sm text-muted">{hint}</p>}
      {error && <p id={`${iid}-err`} role="alert" className="text-sm text-danger">{error}</p>}
    </div>
  )
})
Textarea.displayName = 'Textarea'
