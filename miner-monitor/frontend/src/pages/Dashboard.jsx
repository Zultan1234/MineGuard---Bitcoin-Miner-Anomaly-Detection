import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { useMiners } from '../hooks/useMiners.js'
import { api } from '../utils/api.js'
import MinerCard from '../components/MinerCard.jsx'

const STAT_ICONS = {
  GREEN:   { Icon: CheckCircle,  color: 'var(--green)'  },
  YELLOW:  { Icon: AlertTriangle,color: 'var(--yellow)' },
  RED:     { Icon: XCircle,      color: 'var(--red)'    },
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { miners, refresh } = useMiners()
  const [refreshing, setRefreshing] = useState(false)

  const doRefresh = useCallback(async () => {
    setRefreshing(true)
    await refresh()
    setRefreshing(false)
  }, [refresh])

  const removeMiner = useCallback(async (minerId) => {
    if (!window.confirm('Remove this miner? All collected data will be deleted.')) return
    try {
      await api.miners.delete(minerId)
      await refresh()
    } catch (e) {
      alert(`Failed to remove miner: ${e.message}`)
    }
  }, [refresh])
  useEffect(() => {
    const t = setInterval(doRefresh, 30_000)
    return () => clearInterval(t)
  }, [doRefresh])

  const counts = miners.reduce((acc, m) => {
    acc[m.status || 'UNKNOWN'] = (acc[m.status || 'UNKNOWN'] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 3 }}>Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            {miners.length} miner{miners.length !== 1 ? 's' : ''} registered
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={doRefresh} disabled={refreshing}>
            <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/setup')}>
            <Plus size={14} />
            Add Miner
          </button>
        </div>
      </div>

      {/* Summary stats */}
      {miners.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
          {['GREEN', 'YELLOW', 'RED'].map(s => {
            const { Icon, color } = STAT_ICONS[s]
            return (
              <div key={s} className="card" style={{
                display: 'flex', alignItems: 'center', gap: 12,
                borderColor: (counts[s] || 0) > 0 && s !== 'GREEN' ? color + '40' : 'var(--border)',
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: `${color}15`, border: `1px solid ${color}30`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon size={18} color={color} />
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 600, color, lineHeight: 1 }}>
                    {counts[s] || 0}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {s === 'GREEN' ? 'Normal' : s === 'YELLOW' ? 'Anomaly' : 'Critical'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Miner grid */}
      {miners.length === 0 ? (
        <EmptyState navigate={navigate} />
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: '1rem',
        }}>
          {miners.map(m => <MinerCard key={m.id} miner={m} onRemove={() => removeMiner(m.id)} />)}
        </div>
      )}
    </div>
  )
}

function EmptyState({ navigate }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '50vh',
      gap: 16, color: 'var(--text-muted)',
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: 16,
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5">
          <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
          No miners connected yet
        </div>
        <div style={{ fontSize: 13 }}>
          Add your first miner to start monitoring
        </div>
      </div>
      <button className="btn btn-primary" onClick={() => navigate('/setup')}>
        <Plus size={14} />
        Add your first miner
      </button>
    </div>
  )
}
