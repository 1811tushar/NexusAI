import { cn } from '@/common/utils/cn'
interface Props { checked: boolean; onCheckedChange: (v: boolean) => void; label: string; disabled?: boolean }
export function Switch({ checked, onCheckedChange, label, disabled }: Props) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onCheckedChange(!checked)}
      className={cn('relative h-6 w-11 shrink-0 rounded-full border border-line-strong transition-colors disabled:opacity-50', checked ? 'bg-accent' : 'bg-line')}>
      <span aria-hidden className={cn('absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow-sm transition-all', checked ? 'left-[1.375rem]' : 'left-0.5')} />
    </button>
  )
}
