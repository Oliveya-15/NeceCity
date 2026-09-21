import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

/**
 * Horizontal bar chart used for "count by X" breakdowns. Deliberately not
 * a pie/donut - a sorted horizontal bar list reads counts more precisely
 * and scales better to 6+ categories without a legend.
 */
export default function DistributionChart({ data, colorFn, height = 260 }) {
  if (!data || data.length === 0) return null

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 4 }}>
        <CartesianGrid horizontal={false} stroke="#E2E8F0" />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: '#5B6472' }} axisLine={{ stroke: '#E2E8F0' }} tickLine={false} />
        <YAxis
          type="category"
          dataKey="label"
          width={140}
          tick={{ fontSize: 12, fill: '#33415A' }}
          axisLine={{ stroke: '#E2E8F0' }}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: '#F5F7FA' }}
          contentStyle={{ borderRadius: 6, borderColor: '#E2E8F0', fontSize: 13 }}
        />
        <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={16}>
          {data.map((entry, index) => (
            <Cell key={entry.label} fill={colorFn ? colorFn(entry, index) : '#0B2A52'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
