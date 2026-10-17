import * as M from '@radix-ui/react-dropdown-menu'
import type { ComponentProps } from 'react'
import { cn } from '@/common/utils/cn'
export const DropdownMenu = M.Root
export const DropdownMenuTrigger = M.Trigger
export const DropdownMenuContent = ({ className, ...p }: ComponentProps<typeof M.Content>) => (
  <M.Portal><M.Content align="end" sideOffset={6} className={cn('z-50 min-w-48 rounded-md border border-line bg-raised p-1 shadow-md', className)} {...p} /></M.Portal>
)
export const DropdownMenuItem = ({ className, ...p }: ComponentProps<typeof M.Item>) => (
  <M.Item className={cn('flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-accent-soft', className)} {...p} />
)
export const DropdownMenuLabel = ({ className, ...p }: ComponentProps<typeof M.Label>) => <M.Label className={cn('px-2 py-1 text-xs text-muted', className)} {...p} />
export const DropdownMenuSeparator = () => <M.Separator className="my-1 h-px bg-line" />
