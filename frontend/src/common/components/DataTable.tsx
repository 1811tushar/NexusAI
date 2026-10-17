import { Table, TBody, TD, TH, THead, TR } from './ui/Table'
type Cell = string | number | null
/** Preview table for SQL/STATS evidence. Scrolls inside its container. */
export function DataTable({ columns, rows, truncated, caption }: { columns: string[]; rows: Cell[][]; truncated?: boolean; caption?: string }) {
  return (
    <div className="space-y-1">
      <Table aria-label={caption ?? 'Data preview'}>
        <THead><TR>{columns.map((c) => <TH key={c}>{c}</TH>)}</TR></THead>
        <TBody>{rows.map((r, i) => <TR key={i}>{r.map((v, j) => <TD key={j} className={typeof v === 'number' ? 'text-right tabular-nums' : ''}>{v === null ? 'null' : String(v)}</TD>)}</TR>)}</TBody>
      </Table>
      <p className="text-xs text-muted">{rows.length} rows shown{truncated ? ' (truncated: more rows exist)' : ''}</p>
    </div>
  )
}
