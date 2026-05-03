import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Cpu, BookOpen, MessageSquare, Settings, Activity } from 'lucide-react'
import Dashboard from './pages/Dashboard.jsx'
import Setup from './pages/Setup.jsx'
import Training from './pages/Training.jsx'
import Chat from './pages/Chat.jsx'
import { useLiveSocket } from './hooks/useLiveSocket.js'
import { useMiners } from './hooks/useMiners.js'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/setup',     icon: Cpu,             label: 'Add Miner' },
  { to: '/training',  icon: BookOpen,        label: 'Training' },
  { to: '/chat',      icon: MessageSquare,   label: 'Chat' },
]

export default function App() {
  const { connected } = useLiveSocket()
  const { miners } = useMiners()

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220, flexShrink: 0,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        padding: '1.5rem 0',
      }}>
        {/* Logo */}
        <div style={{ padding: '0 1.25rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--accent-dim)', border: '1px solid var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Activity size={16} color="var(--accent)" />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, letterSpacing: '-0.01em' }}>MinerMonitor</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                v1.0
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '1rem 0.75rem', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderRadius: 8,
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                background: isActive ? 'var(--accent-dim)' : 'transparent',
                fontWeight: 500, fontSize: 13,
                transition: 'var(--transition)',
                textDecoration: 'none',
                border: isActive ? '1px solid var(--accent)' : '1px solid transparent',
              })}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Miner status pills at bottom of sidebar */}
        {miners.length > 0 && (
          <div style={{ padding: '1rem 1.25rem', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Miners
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {miners.slice(0, 5).map(m => (
                <MinerPill key={m.id} miner={m} />
              ))}
            </div>
          </div>
        )}

        {/* WS connection indicator */}
        <div style={{
          margin: '0.75rem 1.25rem 0',
          padding: '6px 10px',
          borderRadius: 6,
          background: connected ? 'var(--green-dim)' : 'var(--bg-raised)',
          border: `1px solid ${connected ? 'var(--green-glow)' : 'var(--border)'}`,
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 11, color: connected ? 'var(--green)' : 'var(--text-muted)',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: connected ? 'var(--green)' : 'var(--text-muted)',
          }} className={connected ? 'pulse-green' : ''} />
          {connected ? 'Live' : 'Disconnected'}
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg-base)' }}>
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/setup"    element={<Setup />} />
          <Route path="/training" element={<Training />} />
          <Route path="/chat"     element={<Chat />} />
          <Route path="/chat/:minerId" element={<Chat />} />
        </Routes>
      </main>
    </div>
  )
}

function MinerPill({ miner }) {
  const statusColor = {
    GREEN: 'var(--green)', YELLOW: 'var(--yellow)',
    RED: 'var(--red)', UNKNOWN: 'var(--text-muted)',
  }
  const color = statusColor[miner.status] || statusColor.UNKNOWN
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{miner.name}</span>
    </div>
  )
}
