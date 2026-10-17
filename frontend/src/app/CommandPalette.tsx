import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dialog, DialogContent } from '@/common/components/ui/Dialog'
import { useHotkeys } from '@/common/hooks/useHotkeys'
import { cn } from '@/common/utils/cn'
import { useAuthStore } from '@/features/auth/authStore'
import { itemsFor } from './navItems'

/** Ctrl/Cmd+K: jump to any page the role can reach (FE-SH-05). */
export function CommandPalette() {
  const role = useAuthStore((s) => s.user?.role)
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState(''); const [active, setActive] = useState(0)
  const toggle = useCallback(() => { setOpen((o) => !o); setQ(''); setActive(0) }, [])
  useHotkeys('mod+k', toggle)
  const results = useMemo(() => (role ? itemsFor(role).filter((i) => i.label.toLowerCase().includes(q.trim().toLowerCase())) : []), [role, q])
  const go = (to: string) => { setOpen(false); nav(to) }
  if (!role) return null
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent title="Go to" description="Type to filter. Use the arrow keys and Enter.">
        <input autoFocus aria-label="Filter pages" role="combobox" aria-expanded aria-controls="palette-list" aria-activedescendant={results[active] ? `pal-${active}` : undefined}
          value={q} onChange={(e) => { setQ(e.target.value); setActive(0) }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
            if (e.key === 'Enter' && results[active]) go(results[active].to)
          }}
          className="h-10 w-full rounded-md border border-line-strong bg-surface px-3" placeholder="Search pages" />
        <ul id="palette-list" role="listbox" aria-label="Pages" className="mt-2 max-h-64 overflow-y-auto">
          {results.length === 0 && <li className="p-2 text-sm text-muted">No pages match.</li>}
          {results.map((r, i) => (
            <li key={r.to} id={`pal-${i}`} role="option" aria-selected={i === active} onClick={() => go(r.to)} onMouseEnter={() => setActive(i)}
              className={cn('flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm', i === active && 'bg-accent-soft')}><r.icon className="h-4 w-4" aria-hidden />{r.label}</li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
