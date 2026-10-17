import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/common/utils/cn'

export const Dialog = D.Root
export const DialogTrigger = D.Trigger
export const DialogClose = D.Close

interface ContentProps { title: string; description?: string; children: ReactNode; className?: string; side?: 'center' | 'right' }
/** Focus is trapped and returned, Esc closes (Radix). Also serves as Sheet via side="right". */
export function DialogContent({ title, description, children, className, side = 'center' }: ContentProps) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-50 bg-black/50" />
      <D.Content className={cn(
        'fixed z-50 border border-line bg-raised p-6 shadow-md',
        side === 'center' ? 'left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg' : 'right-0 top-0 h-full w-full max-w-md overflow-y-auto',
        className)}>
        <D.Title className="pr-8 text-lg font-semibold">{title}</D.Title>
        <D.Description className={description ? 'mt-1 text-sm text-muted' : 'sr-only'}>{description ?? title}</D.Description>
        <div className="mt-4">{children}</div>
        <D.Close aria-label="Close" className="absolute right-3 top-3 rounded-md p-1 text-muted hover:text-ink"><X className="h-4 w-4" aria-hidden /></D.Close>
      </D.Content>
    </D.Portal>
  )
}
export const Sheet = D.Root
export const SheetTrigger = D.Trigger
export const SheetContent = (p: Omit<ContentProps, 'side'>) => <DialogContent side="right" {...p} />
