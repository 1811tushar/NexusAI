import type { HTMLAttributes } from 'react'
import { cn } from '@/common/utils/cn'
export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('rounded-lg border border-line bg-surface p-4', className)} {...p} />
)
