import * as T from '@radix-ui/react-tabs'
import type { ComponentProps } from 'react'
import { cn } from '@/common/utils/cn'
export const Tabs = T.Root
export const TabsList = ({ className, ...p }: ComponentProps<typeof T.List>) => <T.List className={cn('flex gap-1 border-b border-line', className)} {...p} />
export const TabsTrigger = ({ className, ...p }: ComponentProps<typeof T.Trigger>) => (
  <T.Trigger className={cn('-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted data-[state=active]:border-accent data-[state=active]:font-semibold data-[state=active]:text-ink', className)} {...p} />
)
export const TabsContent = ({ className, ...p }: ComponentProps<typeof T.Content>) => <T.Content className={cn('pt-4', className)} {...p} />
