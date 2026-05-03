export default function StatusBadge({ status, size = 'md', pulse = false }) {
  const map = {
    GREEN:   { label: 'Normal',   cls: 'badge-green',  dot: 'var(--green)'  },
    YELLOW:  { label: 'Anomaly',  cls: 'badge-yellow', dot: 'var(--yellow)' },
    RED:     { label: 'Critical', cls: 'badge-red',    dot: 'var(--red)'    },
    UNKNOWN: { label: 'Unknown',  cls: 'badge-muted',  dot: 'var(--text-muted)' },
  }
  const { label, cls, dot } = map[status] || map.UNKNOWN
  const sz = size === 'lg' ? { fontSize: 12, padding: '3px 10px' } : {}

  return (
    <span className={`badge ${cls}`} style={sz}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: dot, display: 'inline-block',
        ...(pulse && status !== 'GREEN' ? { animation: 'pulse-ring 2s ease-out infinite' } : {}),
      }} />
      {label}
    </span>
  )
}
