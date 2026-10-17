import * as T from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <T.Provider delayDuration={300}>
      <T.Root><T.Trigger asChild>{children}</T.Trigger>
        <T.Portal><T.Content sideOffset={6} className="z-50 rounded-md bg-ink px-2 py-1 text-xs text-bg">{label}</T.Content></T.Portal>
      </T.Root>
    </T.Provider>
  )
}
