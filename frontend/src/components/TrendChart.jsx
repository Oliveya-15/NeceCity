import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function TrendChart({ points }) {
  if (!points || points.length === 0) return null
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
        <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#5B6472' }} axisLine={{ stroke: '#E2E8F0' }} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5B6472' }} axisLine={{ stroke: '#E2E8F0' }} tickLine={false} />
        <Tooltip contentStyle={{ borderRadius: 6, borderColor: '#E2E8F0', fontSize: 13 }} />
        <Line type="monotone" dataKey="count" stroke="#FD6001" strokeWidth={2.5} dot={{ r: 3, fill: '#FD6001' }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
