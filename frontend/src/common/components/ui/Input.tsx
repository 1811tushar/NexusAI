import { forwardRef, useId, type InputHTMLAttributes } from 'react'
import { cn } from '@/common/utils/cn'

interface Props extends InputHTMLAttributes<HTMLInputElement> { label: string; error?: string }
/** Labelled input with inline error wired through aria-describedby (FE-A11-02). */
export const Input = forwardRef<HTMLInputElement, Props>(({ label, error, className, id, ...p }, ref) => {
  const auto = useId(); const iid = id ?? auto; const eid = `${iid}-err`
  return (
    <div className="space-y-1">
      <label htmlFor={iid} className="block text-sm font-medium">{label}</label>
      <input ref={ref} id={iid} aria-invalid={!!error} aria-describedby={error ? eid : undefined}
        className={cn('h-10 w-full rounded-md border bg-surface px-3 text-ink placeholder:text-muted', error ? 'border-danger' : 'border-line-strong', className)} {...p} />
      {error && <p id={eid} role="alert" className="text-sm text-danger">{error}</p>}
    </div>
  )
})
Input.displayName = 'Input'
