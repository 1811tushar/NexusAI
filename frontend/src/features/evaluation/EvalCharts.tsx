import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'

const pct = (v: number) => `${Math.round(v * 100)}%`
export function ComparisonChart({ data }: { data: { system: string; correctness: number; grounded: number; hallucination: number }[] }) {
  return (
    <div className="h-72" role="img" aria-label="Bar chart comparing correctness, grounded claims and hallucination rate by system. The table below has the same numbers."><ResponsiveContainer>
      <BarChart data={data}><CartesianGrid stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="system" stroke="var(--text-muted)" /><YAxis tickFormatter={pct} domain={[0, 1]} stroke="var(--text-muted)" /><Tooltip formatter={(v: number) => pct(v)} /><Legend />
        <Bar dataKey="correctness" name="Answer correctness" fill="var(--accent)" /><Bar dataKey="grounded" name="Grounded claims" fill="var(--info)" /><Bar dataKey="hallucination" name="Hallucination rate" fill="var(--danger)" /></BarChart></ResponsiveContainer></div>
  )
}
export function TradeoffChart({ data }: { data: { system: string; tokens: number; correctness: number }[] }) {
  return (
    <div className="h-72" role="img" aria-label="Scatter chart of average tokens against answer correctness per system. The table above has the same numbers."><ResponsiveContainer>
      <ScatterChart><CartesianGrid stroke="var(--border)" strokeDasharray="3 3" /><XAxis type="number" dataKey="tokens" name="Average tokens" stroke="var(--text-muted)" /><YAxis type="number" dataKey="correctness" name="Correctness" tickFormatter={pct} domain={[0, 1]} stroke="var(--text-muted)" /><ZAxis range={[120, 120]} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v: number, n: string) => (n === 'Correctness' ? pct(v) : v)} /><Legend />
        {data.map((d, i) => <Scatter key={d.system} name={d.system} data={[d]} fill={['var(--text-muted)', 'var(--warning)', 'var(--info)', 'var(--accent)'][i % 4]} />)}</ScatterChart></ResponsiveContainer></div>
  )
}
export function AblationChart({ data }: { data: { variant: string; hit: number }[] }) {
  return (
    <div className="h-72" role="img" aria-label="Bar chart of retrieval hit rate by chunking, search mode and reranker variant. The table below has the same numbers."><ResponsiveContainer>
      <BarChart data={data} layout="vertical" margin={{ left: 40 }}><CartesianGrid stroke="var(--border)" strokeDasharray="3 3" /><XAxis type="number" domain={[0, 1]} tickFormatter={pct} stroke="var(--text-muted)" /><YAxis type="category" dataKey="variant" width={170} stroke="var(--text-muted)" /><Tooltip formatter={(v: number) => pct(v)} />
        <Bar dataKey="hit" name="Hit rate" fill="var(--accent)" /></BarChart></ResponsiveContainer></div>
  )
}
