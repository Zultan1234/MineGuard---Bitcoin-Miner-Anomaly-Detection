import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'

export default function FeatureChecklist({ fields = {}, selected = [], onChange }) {
  const [search, setSearch] = useState('')

  const entries = useMemo(() =>
    Object.entries(fields)
      .filter(([k]) => !k.startsWith('_') && !['STATUS', 'When', 'Code', 'Msg', 'Description', 'id'].includes(k))
      .sort(([a], [b]) => a.localeCompare(b)),
    [fields]
  )

  const filtered = search
    ? entries.filter(([k]) => k.toLowerCase().includes(search.toLowerCase()))
    : entries

  const toggle = (key) => {
    if (selected.includes(key)) {
      onChange(selected.filter(k => k !== key))
    } else {
      onChange([...selected, key])
    }
  }

  const selectAll = () => onChange(entries.map(([k]) => k))
  const clearAll = () => onChange([])

  // Recommend obviously useful numeric fields
  const recommended = new Set([
    'GHS 5s', 'GHS av', 'Hardware Errors', 'Device Rejected%',
    'Temperature', 'Fan Speed In', 'Fan Speed Out', 'fan1', 'fan2',
    'temp1', 'temp2', 'temp3', 'Accepted', 'Rejected',
  ])

  return (
    <div>
      {/* Search + bulk actions */}
      <div style={{ display: 'flex', gap: 8, marginBottom: '0.75rem', alignItems: 'center' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            placeholder="Search fields..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: 30 }}
          />
        </div>
        <button className="btn btn-sm" onClick={selectAll}>All</button>
        <button className="btn btn-sm" onClick={clearAll}>Clear</button>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
        {selected.length} / {entries.length} features selected
      </div>

      {/* Feature grid */}
      <div style={{
        maxHeight: 320, overflowY: 'auto',
        border: '1px solid var(--border)',
        borderRadius: 8,
      }}>
        {filtered.map(([key, value], i) => {
          const isSelected = selected.includes(key)
          const isRec = recommended.has(key)
          return (
            <div
              key={key}
              onClick={() => toggle(key)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 12px',
                cursor: 'pointer',
                background: isSelected ? 'var(--accent-dim)' : i % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-raised)',
                borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none',
                transition: 'background 0.1s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {/* Checkbox */}
                <div style={{
                  width: 14, height: 14, borderRadius: 3,
                  border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border-bright)'}`,
                  background: isSelected ? 'var(--accent)' : 'transparent',
                  flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {isSelected && (
                    <svg width="8" height="8" viewBox="0 0 8 8">
                      <path d="M1.5 4l2 2 3-3" stroke="var(--bg-base)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                }}>
                  {key}
                </span>
                {isRec && (
                  <span style={{
                    fontSize: 9, padding: '1px 5px', borderRadius: 3,
                    background: 'var(--accent-dim)', color: 'var(--accent)',
                    letterSpacing: '0.05em',
                  }}>
                    SUGGESTED
                  </span>
                )}
              </div>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {typeof value === 'number' ? value.toFixed(4) : String(value).slice(0, 20)}
              </span>
            </div>
          )
        })}
        {filtered.length === 0 && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No fields match "{search}"
          </div>
        )}
      </div>
    </div>
  )
}
