import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, RefreshCw, WifiOff, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { api } from '../utils/api.js'
import { useLiveSocket } from '../hooks/useLiveSocket.js'
import StatusBadge from './StatusBadge.jsx'
import AnomalyChart from './AnomalyChart.jsx'

const STATUS_COLORS = {
  GREEN:   'var(--green)',
  YELLOW:  'var(--yellow)',
  RED:     'var(--red)',
  OFFLINE: 'var(--text-muted)',
  UNKNOWN: 'var(--text-muted)',
}
const DEV_COLOR = { green:'var(--green)', yellow:'var(--yellow)', red:'var(--red)' }
const DEV_BG    = { green:'var(--green-dim)', yellow:'var(--yellow-dim)', red:'var(--red-dim)' }

// Cumulative fields — their raw value always increases. We show delta (change/interval).
const CUMULATIVE = new Set([
  "Hardware Errors","chain_hw1","chain_hw2","chain_hw3","chain_hw4",
  "no_matching_work","Accepted","Rejected","Discarded",
])

export default function MinerCard({ miner, onRemove }) {
  const navigate = useNavigate()
  const [status,     setStatus]     = useState(miner.status || 'UNKNOWN')
  const [values,     setValues]     = useState({})
  const [violations, setViolations] = useState([])
  const [mlScore,    setMlScore]    = useState(null)
  const [severity,   setSeverity]   = useState('normal')
  const [deviations, setDeviations] = useState([])
  const [explanation, setExplanation] = useState(null)
  const [telemetry,  setTelemetry]  = useState([])
  const [loading,    setLoading]    = useState(false)
  const [fetchError, setFetchError] = useState('')
  const [offline,    setOffline]    = useState(false)
  const [expanded,   setExpanded]   = useState(false)
  const [showDelta,  setShowDelta]  = useState(true)  // toggle cumulative -> delta

  const fetchStatus = useCallback(async () => {
    setLoading(true); setFetchError('')
    try {
      const s = await api.miners.status(miner.id)
      setStatus(s.status || 'UNKNOWN')
      setValues(s.current_values || {})
      setViolations(s.rule_violations || [])
      setMlScore(s.ml?.isolation_forest?.anomaly_score ?? null)
      setSeverity(s.ml?.severity || 'normal')
      setDeviations(s.deviations || [])
      setExplanation(s.ml?.explanation || null)
      setOffline(false)
    } catch (e) { setFetchError(e.message) }
    finally { setLoading(false) }
  }, [miner.id])

  const fetchTelemetry = useCallback(async () => {
    try { setTelemetry(await api.miners.telemetry(miner.id, 60)) } catch {}
  }, [miner.id])

  useEffect(() => { fetchStatus(); fetchTelemetry() }, [fetchStatus, fetchTelemetry])

  const onMessage = useCallback((msg) => {
    if (msg.miner_id !== miner.id || msg.type !== 'telemetry') return
    if (msg.offline) { setStatus('OFFLINE'); setOffline(true); setValues({}); return }
    setStatus(msg.status || 'UNKNOWN')
    setValues(msg.values || {})
    setViolations(msg.rule_violations || [])
    setMlScore(msg.if_score ?? null)
    setSeverity(msg.severity || 'normal')
    setDeviations(msg.deviations || [])
    setExplanation(msg.explanation || null)
    setOffline(false); setFetchError('')
    fetchTelemetry()
  }, [miner.id, fetchTelemetry])
  useLiveSocket(onMessage)

  const displayValues = Object.fromEntries(
    Object.entries(values).filter(([k]) => !k.startsWith('_'))
  )
  const accentColor = STATUS_COLORS[status] || STATUS_COLORS.UNKNOWN
  const isAlert = status !== 'GREEN' && status !== 'UNKNOWN' && status !== 'OFFLINE'

  // Auto-message for chatbot
  const anomalySummary = deviations.filter(d => d.status !== 'green').map(d =>
    `${d.feature}: ${d.current} (${d.pct_deviation > 0 ? '+' : ''}${d.pct_deviation}% from baseline ${d.baseline_mean})`
  ).join('\n')

  const hasCumulativeFeatures = Object.keys(displayValues).some(k => CUMULATIVE.has(k))

  return (
    <div className="card" style={{
      borderColor: isAlert ? accentColor+'60' : offline ? '#33333360' : 'var(--border)',
      boxShadow: isAlert ? `0 0 20px ${accentColor}18` : 'none',
      opacity: offline ? 0.75 : 1,
      transition: 'all 0.3s ease',
    }}>

      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'0.75rem' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:3 }}>
            <span style={{ fontWeight:600, fontSize:15 }}>{miner.name}</span>
            {offline
              ? <span className="badge badge-muted"><WifiOff size={9}/> Offline</span>
              : <StatusBadge status={status} pulse={status==='RED'} />
            }
            {severity === 'critical' && !offline && (
              <span style={{ fontSize:10, padding:'2px 6px', borderRadius:4,
                background:'var(--red-dim)', color:'var(--red)', border:'1px solid var(--red-glow)' }}>
                CRITICAL
              </span>
            )}
          </div>
          <div className="mono" style={{ fontSize:11, color:'var(--text-muted)' }}>
            {miner.ip}:{miner.port}
          </div>
        </div>
        <div style={{ display:'flex', gap:5, alignItems:'center' }}>
          <button className="btn btn-sm" onClick={fetchStatus} disabled={loading} data-tooltip="Refresh">
            <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
          <button className="btn btn-sm btn-primary" data-tooltip="Chat"
            onClick={() => {
              const msg = anomalySummary
                ? `Anomaly on ${miner.name}. Features outside normal range:\n${anomalySummary}\nStatus: ${status}. What is likely wrong and what should I check?`
                : `Current status of ${miner.name}: ${status}. Give me a summary.`
              navigate(`/chat/${miner.id}`, { state: { autoMessage: msg } })
            }}>
            <MessageSquare size={12} />
          </button>
          <button className="btn btn-sm" data-tooltip="Remove miner"
            onClick={onRemove}
            style={{ color:'var(--red)', borderColor:'var(--red-glow)' }}>
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Traffic light */}
      <div style={{ display:'flex', gap:6, marginBottom:'0.75rem' }}>
        {['GREEN','YELLOW','RED'].map(s => (
          <div key={s} style={{
            flex:1, height:4, borderRadius:2,
            background: status===s ? STATUS_COLORS[s] : 'var(--bg-overlay)',
            transition:'background 0.3s ease',
          }}/>
        ))}
      </div>

      {/* Cumulative fields toggle */}
      {hasCumulativeFeatures && !offline && (
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:'0.5rem',
          fontSize:11, color:'var(--text-muted)' }}>
          <button onClick={() => setShowDelta(!showDelta)} style={{
            display:'flex', alignItems:'center', gap:5, background:'none', border:'none',
            cursor:'pointer', color: showDelta ? 'var(--accent)' : 'var(--text-muted)',
            padding:0, fontSize:11,
          }}>
            {showDelta ? <ToggleRight size={16} color="var(--accent)"/> : <ToggleLeft size={16}/>}
            {showDelta ? 'Showing deltas (change/interval)' : 'Showing raw cumulative values'}
          </button>
        </div>
      )}

      {/* Offline notice */}
      {offline && (
        <div style={{ padding:'8px 12px', borderRadius:6, marginBottom:'0.75rem',
          background:'var(--bg-raised)', border:'1px solid var(--border)',
          fontSize:12, color:'var(--text-muted)', display:'flex', alignItems:'center', gap:6 }}>
          <WifiOff size={13}/> Miner not responding — may be turned off
        </div>
      )}
      {fetchError && (
        <div style={{ fontSize:11, padding:'6px 8px', borderRadius:6, marginBottom:'0.75rem',
          background:'var(--red-dim)', color:'var(--red)', border:'1px solid var(--red-glow)' }}>
          {fetchError}
        </div>
      )}

      {/* Feature deviations (after training) */}
      {deviations.length > 0 && !offline ? (
        <div style={{ marginBottom:'0.75rem' }}>
          <div style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase',
            letterSpacing:'0.05em', marginBottom:5 }}>
            Feature Deviations from Baseline
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4 }}>
            {(expanded ? deviations : deviations.slice(0,6)).map(d => {
              const isCumul = CUMULATIVE.has(d.feature)
              return (
                <div key={d.feature} style={{
                  padding:'5px 8px', borderRadius:5,
                  background: DEV_BG[d.status] || 'var(--bg-raised)',
                  border:`1px solid ${DEV_COLOR[d.status] || 'var(--border)'}22`,
                  display:'flex', justifyContent:'space-between', alignItems:'center',
                }}>
                  <div style={{ minWidth:0 }}>
                    <span style={{ fontSize:10, color:'var(--text-muted)',
                      overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
                      display:'block', maxWidth:100 }}>
                      {d.feature}{isCumul && showDelta ? ' Δ' : ''}
                    </span>
                    <span style={{ fontSize:9, color:'var(--text-muted)' }}>
                      {d.current} vs {d.baseline_mean}
                    </span>
                  </div>
                  <span className="mono" style={{ fontSize:11, fontWeight:600, flexShrink:0,
                    color: DEV_COLOR[d.status] || 'var(--text-primary)' }}>
                    {d.pct_deviation > 0 ? '+' : ''}{d.pct_deviation}%
                  </span>
                </div>
              )
            })}
          </div>
          {deviations.length > 6 && (
            <button onClick={() => setExpanded(!expanded)} style={{
              marginTop:5, fontSize:10, color:'var(--accent)', background:'none',
              border:'none', cursor:'pointer', padding:0 }}>
              {expanded ? '▲ Show less' : `▼ Show all ${deviations.length} features`}
            </button>
          )}
        </div>
      ) : Object.keys(displayValues).length > 0 && !offline ? (
        // Raw values before baseline is established
        <div style={{ marginBottom:'0.75rem' }}>
          <div style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase',
            letterSpacing:'0.05em', marginBottom:5 }}>
            Current Values (no baseline yet — train to enable comparison)
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'6px 12px' }}>
            {Object.entries(displayValues).slice(0,8).map(([k,v]) => {
              const isCumul = CUMULATIVE.has(k)
              return (
                <div key={k}>
                  <div style={{ fontSize:10, color:'var(--text-muted)', marginBottom:1,
                    textTransform:'uppercase', letterSpacing:'0.05em',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {k}{isCumul && showDelta ? ' (Δ)' : ''}
                  </div>
                  <div className="mono" style={{ fontSize:13, color:'var(--text-primary)', fontWeight:500 }}>
                    {typeof v === 'number' ? v.toFixed(2) : String(v)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : !offline && (
        <div style={{ color:'var(--text-muted)', fontSize:12, marginBottom:'0.75rem' }}>
          {loading ? 'Fetching...' : 'Waiting for first poll...'}
        </div>
      )}

      {/* Rule violations */}
      {violations.length > 0 && !offline && violations.slice(0,2).map((v,i) => (
        <div key={i} style={{
          fontSize:11, padding:'4px 8px', borderRadius:4, marginBottom:3,
          background: v.severity==='red'?'var(--red-dim)':'var(--yellow-dim)',
          color: v.severity==='red'?'var(--red)':'var(--yellow)',
          border:`1px solid ${v.severity==='red'?'var(--red-glow)':'var(--yellow-glow)'}`,
        }}>{v.message}</div>
      ))}

      {/* ML anomaly score */}
      {mlScore !== null && !offline && (
        <div style={{ marginBottom:'0.5rem' }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
            <span style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.05em' }}>
              Anomaly Score
            </span>
            <span className="mono" style={{ fontSize:11,
              color: mlScore>0.6?'var(--yellow)':'var(--text-muted)' }}>
              {(mlScore*100).toFixed(1)}%
            </span>
          </div>
          <div style={{ height:3, background:'var(--bg-overlay)', borderRadius:2, overflow:'hidden' }}>
            <div style={{ height:'100%', borderRadius:2,
              width:`${Math.min(100,mlScore*100)}%`,
              background: mlScore>0.75?'var(--red)':mlScore>0.5?'var(--yellow)':'var(--green)',
              transition:'width 0.5s ease' }}/>
          </div>
        </div>
      )}

      {/* Explanation — narrative + confidence + failure signature */}
      {explanation && explanation.is_anomaly && !offline && (
        <div style={{
          padding:'8px 10px', borderRadius:6, marginBottom:'0.5rem',
          background: 'var(--bg-raised)', border:'1px solid var(--border)',
        }}>
          {/* Confidence badge + signature */}
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:5 }}>
            {explanation.confidence && (
              <span style={{
                fontSize:9, padding:'1px 5px', borderRadius:3, fontWeight:600,
                textTransform:'uppercase', letterSpacing:'0.05em',
                background: explanation.confidence==='high'?'var(--green-dim)':
                            explanation.confidence==='medium'?'var(--yellow-dim)':'var(--bg-overlay)',
                color: explanation.confidence==='high'?'var(--green)':
                       explanation.confidence==='medium'?'var(--yellow)':'var(--text-muted)',
                border: `1px solid ${explanation.confidence==='high'?'var(--green-glow)':
                         explanation.confidence==='medium'?'var(--yellow-glow)':'var(--border)'}`,
              }}>
                {explanation.confidence} confidence
              </span>
            )}
            {explanation.signature && (
              <span style={{ fontSize:10, color:'var(--accent)', fontWeight:500 }}>
                {explanation.signature.label}
              </span>
            )}
          </div>
          {/* Narrative */}
          <div style={{ fontSize:11, color:'var(--text-secondary)', lineHeight:1.5, marginBottom:6 }}>
            {explanation.narrative}
          </div>
          {/* Top ranked features from fusion */}
          {explanation.ranked_features?.length > 0 && (
            <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
              {explanation.ranked_features.slice(0,3).map((f, i) => (
                <span key={i} style={{
                  fontSize:9, padding:'2px 6px', borderRadius:3,
                  background: f.direction==='anomaly'?'var(--red-dim)':'var(--green-dim)',
                  color: f.direction==='anomaly'?'var(--red)':'var(--green)',
                  border: `1px solid ${f.direction==='anomaly'?'var(--red-glow)':'var(--green-glow)'}`,
                  fontFamily:'var(--font-mono)',
                }}>
                  {f.feature} ({(f.importance*100).toFixed(0)}%)
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sparkline */}
      {telemetry.length > 3 && !offline && (
        <div style={{ marginTop:6 }}>
          <AnomalyChart telemetry={telemetry} height={60} compact />
        </div>
      )}

      <div style={{ marginTop:8, fontSize:10, color:'var(--text-muted)' }}>
        Last seen: {miner.last_seen ? new Date(miner.last_seen).toLocaleTimeString() : 'never'}
      </div>
    </div>
  )
}
