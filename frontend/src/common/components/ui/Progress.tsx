export function Progress({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(100, Math.round(value)))
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={v} className="h-1.5 w-full overflow-hidden rounded-sm bg-line">
      <div className="h-full bg-accent transition-all" style={{ width: `${v}%` }} />
    </div>
  )
}
