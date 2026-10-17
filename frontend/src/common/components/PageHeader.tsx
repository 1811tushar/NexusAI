import type { ReactNode } from 'react'
export const PageHeader = ({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) => (
  <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div><h1 className="text-2xl font-semibold">{title}</h1>{description && <p className="mt-1 text-muted">{description}</p>}</div>
    {actions}
  </header>
)
