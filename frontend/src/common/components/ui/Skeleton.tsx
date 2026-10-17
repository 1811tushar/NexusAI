import { cn } from '@/common/utils/cn'
export const Skeleton = ({ className }: { className?: string }) => (
  <div aria-hidden className={cn('animate-pulse rounded-md bg-line', className)} />
)
