import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Button } from './Button'
/** aria-label is mandatory (FE-A11-02). */
export const IconButton = forwardRef<HTMLButtonElement, Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> & { label: string; children: ReactNode }>(
  ({ label, children, ...p }, ref) => <Button ref={ref} variant="ghost" size="icon" aria-label={label} {...p}>{children}</Button>)
IconButton.displayName = 'IconButton'
