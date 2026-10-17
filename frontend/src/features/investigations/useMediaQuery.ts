import { useEffect, useState } from 'react'
export function useMediaQuery(query: string): boolean {
  const [m, set] = useState(() => matchMedia(query).matches)
  useEffect(() => {
    const mq = matchMedia(query); const on = () => set(mq.matches)
    on(); mq.addEventListener('change', on); return () => mq.removeEventListener('change', on)
  }, [query])
  return m
}
