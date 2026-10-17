import type { Config } from 'tailwindcss'

const v = (n: string) => `var(--${n})`
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: v('bg'), surface: v('surface'), raised: v('surface-raised'), line: v('border'), 'line-strong': v('border-strong'),
        ink: v('text'), muted: v('text-muted'), accent: v('accent'), 'accent-ink': v('accent-ink'), 'accent-soft': v('accent-soft'),
        success: v('success'), warning: v('warning'), danger: v('danger'), info: v('info'),
        'success-soft': v('success-soft'), 'warning-soft': v('warning-soft'), 'danger-soft': v('danger-soft'), 'info-soft': v('info-soft'),
        'risk-low': v('risk-low'), 'risk-high': v('risk-high'),
        verified: v('verified'), unsupported: v('unsupported'), contradicted: v('contradicted'),
      },
      borderRadius: { sm: v('radius-sm'), md: v('radius-md'), lg: v('radius-lg') },
      boxShadow: { sm: v('shadow-sm'), md: v('shadow-md') },
      fontFamily: { sans: ['"Public Sans Variable"', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
} satisfies Config
