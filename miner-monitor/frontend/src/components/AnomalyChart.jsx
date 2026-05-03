import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, Legend,
} from 'recharts'

const FEATURE_COLORS = [
  '#06b6d4', '#22c55e', '#f59e0b', '#a78bfa', '#f472b6',
  '#34d399', '#fb923c', '#60a5fa',
]

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function AnomalyChart({ telemetry = [], height = 220, compact = false, selectedFeatures }) {
  if (!telemetry.length) return null

  // Build unified dataset: [{timestamp, Feature1: val, Feature2: val, ...}]
  const allFeatures = selectedFeatures || Object.keys(telemetry[0]?.values || {})
  const data = telemetry.map(r => ({
    timestamp: r.timestamp,
    ...r.values,
  }))

  if (compact) {
    // Minimal sparkline — just the first feature
    const feat = allFeatures[0]
    if (!feat) return null
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 2, right: 2, left: -30, bottom: 0 }}>
          <Line
            type="monotone" dataKey={feat}
            stroke="#06b6d4" strokeWidth={1.5}
            dot={false} isAnimationActive={false}
          />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9, fill: '#4a5562' }} />
          <Tooltip
            contentStyle={{ background: '#181d22', border: '1px solid #252c35', borderRadius: 6, fontSize: 11 }}
            labelStyle={{ color: '#8a96a3' }}
            itemStyle={{ color: '#06b6d4' }}
            formatter={(v) => [typeof v === 'number' ? v.toFixed(3) : v, feat]}
            labelFormatter={formatTime}
          />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <div style={{ background: 'var(--bg-surface)', borderRadius: 8, padding: '1rem' }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            tick={{ fontSize: 10, fill: '#4a5562' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#4a5562' }}
            tickLine={false}
            axisLine={false}
            width={45}
          />
          <Tooltip
            contentStyle={{ background: '#181d22', border: '1px solid #252c35', borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: '#8a96a3', marginBottom: 4 }}
            labelFormatter={formatTime}
            formatter={(v, name) => [typeof v === 'number' ? v.toFixed(4) : v, name]}
          />
          {allFeatures.length > 1 && (
            <Legend
              iconSize={8}
              wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)', paddingTop: 8 }}
            />
          )}
          {allFeatures.map((feat, i) => (
            <Line
              key={feat}
              type="monotone"
              dataKey={feat}
              stroke={FEATURE_COLORS[i % FEATURE_COLORS.length]}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
