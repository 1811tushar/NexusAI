import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
export interface ChartData { type: 'line' | 'bar'; x: string[]; series: { name: string; values: number[] }[] }
const colors = ['var(--accent)', 'var(--info)', 'var(--warning)', 'var(--danger)']
/** Lazy-loaded (recharts is heavy). Chart is supplemental: the data table carries the same numbers. */
export default function EvidenceChart({ chart }: { chart: ChartData }) {
  const data = chart.x.map((x, i) => Object.fromEntries([['x', x], ...chart.series.map((s) => [s.name, s.values[i] ?? null])]))
  const Chart = chart.type === 'bar' ? BarChart : LineChart
  return (
    <div className="h-56 w-full" role="img" aria-label={`${chart.type} chart of ${chart.series.map((s) => s.name).join(', ')}`}>
      <ResponsiveContainer>
        <Chart data={data}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="x" stroke="var(--text-muted)" /><YAxis stroke="var(--text-muted)" />
          <Tooltip /><Legend />
          {chart.series.map((s, i) => chart.type === 'bar'
            ? <Bar key={s.name} dataKey={s.name} fill={colors[i % colors.length]} />
            : <Line key={s.name} type="monotone" dataKey={s.name} stroke={colors[i % colors.length]} dot={false} />)}
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}
