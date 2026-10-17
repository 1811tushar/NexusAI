import { RefreshCw } from 'lucide-react'
export function LoopNotice({ loop }: { loop: { current: number; max: number; reason: string; focus: string[] } }) {
  return (
    <div role="status" className="rounded-md border border-warning bg-warning-soft p-3 text-sm">
      <p className="flex items-center gap-2 font-medium text-warning"><RefreshCw className="h-4 w-4" aria-hidden />Looping back {loop.current} of {loop.max}: {loop.reason}</p>
      {loop.focus.length > 0 && <ul className="mt-1 list-disc pl-6">{loop.focus.map((f) => <li key={f}>{f}</li>)}</ul>}
    </div>
  )
}
