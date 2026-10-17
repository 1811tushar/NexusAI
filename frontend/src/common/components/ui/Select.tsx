import { forwardRef, useId, type SelectHTMLAttributes } from 'react'
import { cn } from '@/common/utils/cn'
interface Props extends SelectHTMLAttributes<HTMLSelectElement> { label: string; hideLabel?: boolean; options: { value: string; label: string }[] }
/** Native select: fully keyboard and screen-reader accessible, styled with tokens. */
export const Select = forwardRef<HTMLSelectElement, Props>(({ label, hideLabel, options, className, id, ...p }, ref) => {
  const auto = useId(); const iid = id ?? auto
  return (
    <div className="space-y-1">
      <label htmlFor={iid} className={cn('block text-sm font-medium', hideLabel && 'sr-only')}>{label}</label>
      <select ref={ref} id={iid} className={cn('h-10 rounded-md border border-line-strong bg-surface px-3 text-ink', className)} {...p}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
})
Select.displayName = 'Select'
