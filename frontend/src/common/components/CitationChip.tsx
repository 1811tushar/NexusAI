import { Link } from 'react-router-dom'
interface Props { index: number; title: string; to?: string; onClick?: () => void }
const cls = 'inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line-strong bg-accent-soft px-1 text-xs font-medium text-accent'
export function CitationChip({ index, title, to, onClick }: Props) {
  const label = `Source ${index}: ${title}`
  if (to) return <Link to={to} className={cls} aria-label={label} title={title}>{index}</Link>
  return <button type="button" onClick={onClick} className={cls} aria-label={label} title={title}>{index}</button>
}
