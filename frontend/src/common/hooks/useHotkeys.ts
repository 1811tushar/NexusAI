import { useEffect } from 'react'
/** combo like "mod+k" (mod = Ctrl or Cmd). */
export function useHotkeys(combo: string, handler: (e: KeyboardEvent) => void) {
  useEffect(() => {
    const [mod, key] = combo.includes('+') ? combo.split('+') : [null, combo]
    const on = (e: KeyboardEvent) => {
      if (mod === 'mod' && !(e.ctrlKey || e.metaKey)) return
      if (e.key.toLowerCase() === key) { e.preventDefault(); handler(e) }
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [combo, handler])
}
