import { useEffect, useState } from 'react'
export function useDebounce<T>(value: T, ms = 300): T {
  const [v, set] = useState(value)
  useEffect(() => { const t = setTimeout(() => set(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}
