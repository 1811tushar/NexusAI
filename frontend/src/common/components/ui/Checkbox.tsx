import { forwardRef, useId, type InputHTMLAttributes } from 'react'
export const Checkbox = forwardRef<HTMLInputElement, Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { label: string }>(
  ({ label, id, ...p }, ref) => {
    const auto = useId(); const iid = id ?? auto
    return (
      <div className="flex items-center gap-2">
        <input ref={ref} id={iid} type="checkbox" className="h-4 w-4 accent-[var(--accent)]" {...p} />
        <label htmlFor={iid} className="text-sm">{label}</label>
      </div>
    )
  })
Checkbox.displayName = 'Checkbox'
