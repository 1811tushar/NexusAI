import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/common/utils/cn'
/** Wide tables scroll inside their own container, never the page (FE-RS-01). */
export const Table = ({ className, ...p }: HTMLAttributes<HTMLTableElement>) => (
  <div className="overflow-x-auto rounded-lg border border-line"><table className={cn('w-full border-collapse text-left text-sm', className)} {...p} /></div>
)
export const THead = (p: HTMLAttributes<HTMLTableSectionElement>) => <thead className="bg-bg text-muted" {...p} />
export const TBody = (p: HTMLAttributes<HTMLTableSectionElement>) => <tbody className="divide-y divide-line bg-surface" {...p} />
export const TR = (p: HTMLAttributes<HTMLTableRowElement>) => <tr {...p} />
export const TH = ({ className, ...p }: ThHTMLAttributes<HTMLTableCellElement>) => <th scope="col" className={cn('whitespace-nowrap px-3 py-2 font-medium', className)} {...p} />
export const TD = ({ className, ...p }: TdHTMLAttributes<HTMLTableCellElement>) => <td className={cn('px-3 py-2 align-top', className)} {...p} />
