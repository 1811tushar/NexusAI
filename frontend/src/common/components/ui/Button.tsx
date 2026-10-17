import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '@/common/utils/cn'

const button = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-ink hover:opacity-90',
        secondary: 'bg-surface text-ink border border-line-strong hover:bg-accent-soft',
        ghost: 'text-ink hover:bg-accent-soft',
        danger: 'bg-danger text-accent-ink hover:opacity-90',
      },
      size: { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4 text-sm', icon: 'h-10 w-10' },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> { loading?: boolean }

/** Pending state blocks duplicate submits (FE-ZS-02). Icon-only buttons must pass aria-label. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, loading, children, disabled, ...p }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...p}>
    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
    {children}
  </button>
))
Button.displayName = 'Button'
