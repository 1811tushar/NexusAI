import type { ReactNode } from 'react'
export const EmptyState = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="rounded-lg border border-dashed border-line-strong p-8 text-center">
    <h2 className="text-lg font-semibold">{title}</h2>
    {hint && <p className="mt-1 text-muted">{hint}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
)
