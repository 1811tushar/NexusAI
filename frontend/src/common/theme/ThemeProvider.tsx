import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Theme } from '@/common/types/api'

const KEY = 'nx_theme'
const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({ theme: 'SYSTEM', setTheme: () => {} })

function apply(theme: Theme) {
  const dark = theme === 'DARK' || (theme === 'SYSTEM' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, set] = useState<Theme>(() => (localStorage.getItem(KEY) as Theme | null) ?? 'SYSTEM')
  const setTheme = useCallback((t: Theme) => { localStorage.setItem(KEY, t); set(t) }, [])
  useEffect(() => {
    apply(theme)
    if (theme !== 'SYSTEM') return
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const on = () => apply('SYSTEM')
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [theme])
  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export const useTheme = () => useContext(Ctx)
