import type { ReactNode } from 'react'
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
/** Wraps query terms in <mark>. Plain text in, React nodes out: no HTML injection. */
export function highlight(text: string, query: string): ReactNode {
  const terms = query.split(/\s+/).filter((t) => t.length > 1).map(esc)
  if (!terms.length) return text
  const re = new RegExp(`(${terms.join('|')})`, 'gi')
  return text.split(re).map((part, i) => (i % 2 === 1 ? <mark key={i} className="rounded-sm bg-warning-soft px-0.5 text-ink">{part}</mark> : part))
}
