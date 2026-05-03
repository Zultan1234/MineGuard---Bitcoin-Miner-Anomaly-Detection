import { useState, useEffect, useCallback, useRef } from 'react'
import { Play, RefreshCw, CheckCircle, Clock, BarChart2, Zap, Download, Upload, FileText, Table, Loader } from 'lucide-react'
import { api } from '../utils/api.js'
import { useMiners } from '../hooks/useMiners.js'
import AnomalyChart from '../components/AnomalyChart.jsx'

export default function Training() {
  const { miners }           = useMiners()
  const [sel, setSel]        = useState('')
  const [ts, setTs]          = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [evaluation, setEval]   = useState(null)
  const [telemetry, setTele]    = useState([])
  const [targetSamples, setTarget] = useState(240)
  const [loading, setLoading]  = useState(false)
  const [trainBusy, setTrainBusy] = useState(false)
  const [error, setError]      = useState('')
  const [importMsg, setImportMsg] = useState('')
  const [simMsg, setSimMsg]     = useState('')
  const [dataPreview, setDataPreview] = useState(null)
  const [actionLoading, setActionLoading] = useState('')  // which button is loading
  const fileRef = useRef(null)
  const simRef  = useRef(null)
  const dataRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (miners.length > 0 && !sel) setSel(miners[0].id)
  }, [miners, sel])

  const fetchStatus = useCallback(async () => {
    if (!sel) return
    try {
      const s = await api.training.status(sel)
      setTs(s)
      if (s.phase === 'monitoring') {
        try { setBaseline(await api.training.baseline(sel)) } catch {}
        if (s.evaluation) setEval(s.evaluation)
        else try { setEval(await api.training.evaluate(sel)) } catch {}
      }
    } catch (e) { setError(e.message) }
  }, [sel])

  const fetchTele = useCallback(async () => {
    if (!sel) return
    try { setTele(await api.miners.telemetry(sel, 300)) } catch {}
  }, [sel])

  useEffect(() => {
    if (!sel) return
    setTs(null); setBaseline(null); setEval(null); setError(''); setImportMsg(''); setSimMsg(''); setDataPreview(null)
    fetchStatus(); fetchTele()
  }, [sel, fetchStatus, fetchTele])

  useEffect(() => {
    const phase = ts?.phase
    if (phase === 'learning' || phase === 'training') {
      pollRef.current = setInterval(fetchStatus, 3000)
    } else {
      clearInterval(pollRef.current)
      if (phase === 'monitoring') fetchTele()
    }
    return () => clearInterval(pollRef.current)
  }, [ts?.phase, fetchStatus, fetchTele])

  async function startLearning() {
    setActionLoading('learn'); setError('')
    try { await api.training.start(sel, { target_samples: targetSamples }); await fetchStatus() }
    catch (e) { setError(e.message) }
    finally { setActionLoading('') }
  }

  async function trainNow() {
    setTrainBusy(true); setActionLoading('train'); setError('')
    try { await api.training.trainNow(sel); await fetchStatus() }
    catch (e) { setError(e.message) }
    finally { setTrainBusy(false); setActionLoading('') }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setActionLoading('import-model'); setImportMsg(''); setError('')
    try {
      const result = await api.training.importModel(sel, file)
      setImportMsg(result.message)
      await fetchStatus()
    } catch (e) { setError(`Import failed: ${e.message}`) }
    finally { setActionLoading(''); e.target.value = '' }
  }

  async function handleImportData(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setActionLoading('import-data'); setImportMsg(''); setError(''); setDataPreview(null)
    try {
      const result = await api.training.importData(sel, file)
      setImportMsg(result.message)
      // Show a preview of what was imported
      setDataPreview({
        imported: result.imported,
        skipped: result.skipped,
        total: result.total_rows,
      })
      await fetchStatus()
    } catch (e) { setError(`Data import failed: ${e.message}`) }
    finally { setActionLoading(''); e.target.value = '' }
  }

  async function handleSimulate(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setActionLoading('simulate'); setSimMsg(''); setError('')
    try {
      const result = await api.training.simulate(sel, file)
      setSimMsg(result.message)
    } catch (e) { setError(`Simulation failed: ${e.message}`) }
    finally { setActionLoading(''); e.target.value = '' }
  }

  const phase = ts?.phase
  const samples = ts?.sample_count ?? 0
  const canTrain = samples >= 30

  return (
    <div style={{ padding:'1.5rem', maxWidth:820, margin:'0 auto' }}>
      <div style={{ marginBottom:'1.5rem' }}>
        <h1 style={{ fontSize:20, fontWeight:600, marginBottom:4 }}>Training</h1>
        <p style={{ color:'var(--text-muted)', fontSize:13 }}>
          The model uses a fixed set of 16 validated features: hashrate, per-board rates, chip temperatures, fans, and 3 derived indicators.
        </p>
      </div>

      <div className="card" style={{ marginBottom:'1rem', fontSize:12, color:'var(--text-secondary)', lineHeight:1.7 }}>
        <strong style={{ color:'var(--accent)' }}>Feature set (fixed, validated in notebooks):</strong>{' '}
        GHS 5s, GHS av, chain_rate1-4, temp2_1-4, temp_max, fan1, fan2, chain_rate_imbalance, temp_differential, hash_efficiency.
        These 16 features capture hashrate health, thermal status, cooling, and per-board balance. All other fields (pool data, cumulative counters, constant values) are excluded to prevent false anomalies.
      </div>

      {miners.length === 0 ? (
        <div className="card" style={{ textAlign:'center', padding:'2.5rem', color:'var(--text-muted)' }}>
          No miners registered. <a href="/setup">Add a miner</a> first.
        </div>
      ) : (
        <>
          <div className="card" style={{ marginBottom:'1rem' }}>
            <label>Select miner</label>
            <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop:6 }}>
              {miners.map(m => (
                <button key={m.id} className={`btn ${sel===m.id?'btn-primary':''}`} onClick={() => setSel(m.id)}>
                  {m.name}
                </button>
              ))}
            </div>
          </div>

          {ts && (
            <>
              <div className="card" style={{ marginBottom:'1rem' }}>
                <PhaseDisplay status={ts} />
              </div>

              <div className="card" style={{ marginBottom:'1rem' }}>
                <h3 style={{ fontSize:13, fontWeight:600, marginBottom:'1rem' }}>Actions</h3>

                {(phase === 'idle' || phase === 'monitoring') && (
                  <div>
                    <label style={{ marginBottom:8 }}>Target samples</label>
                    <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:'1rem' }}>
                      {[{v:60,l:'30 min'},{v:240,l:'2 hours ✓'},{v:480,l:'4 hours'},{v:1440,l:'12 hours'}].map(({v,l}) => (
                        <button key={v} className={`btn btn-sm ${targetSamples===v?'btn-primary':''}`} onClick={() => setTarget(v)}>{l}</button>
                      ))}
                    </div>
                    <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                      <ActionButton label={phase==='monitoring'?'Restart Learning':'Start Learning Phase'}
                        icon={<Play size={13}/>} loading={actionLoading==='learn'} onClick={startLearning} />
                      {canTrain && (
                        <ActionButton label="Train on existing data"
                          icon={<Zap size={13}/>} loading={actionLoading==='train'} onClick={trainNow} />
                      )}
                    </div>
                  </div>
                )}

                {phase === 'learning' && (
                  <div>
                    <p style={{ fontSize:12, color:'var(--text-muted)', marginBottom:'0.75rem' }}>
                      Collecting baseline data. Keep miner running normally.
                    </p>
                    <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                      <ActionButton label={canTrain?`Train Now (${samples} samples)`:'Need 30+ samples'}
                        icon={<Zap size={13}/>} loading={actionLoading==='train'}
                        onClick={trainNow} disabled={!canTrain} />
                      <button className="btn" onClick={fetchStatus}><RefreshCw size={13}/> Refresh</button>
                    </div>
                  </div>
                )}

                {phase === 'training' && (
                  <div style={{ display:'flex', alignItems:'center', gap:10, color:'var(--accent)', fontSize:13 }}>
                    <Loader size={16} className="spin" />
                    Training on 16 features... updating every 3 seconds.
                  </div>
                )}

                <hr style={{ margin:'1rem 0' }} />

                {/* Import/Export/Simulate */}
                <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
                  {phase === 'monitoring' && (
                    <>
                      <button className="btn" onClick={() => api.training.exportModel(sel)}>
                        <Download size={13}/> Export Model
                      </button>
                      <button className="btn" onClick={() => api.training.exportData(sel, 'csv')}>
                        <FileText size={13}/> Export CSV
                      </button>
                      <button className="btn" onClick={() => api.training.exportData(sel, 'excel')}>
                        <Table size={13}/> Export Excel
                      </button>
                    </>
                  )}
                  <ActionButton label="Import Model (.pkl)"
                    icon={<Upload size={13}/>} loading={actionLoading==='import-model'}
                    onClick={() => fileRef.current?.click()} />
                  <input ref={fileRef} type="file" accept=".pkl" style={{ display:'none' }} onChange={handleImport} />

                  <ActionButton label="Import Data (CSV/Excel)"
                    icon={<Upload size={13}/>} loading={actionLoading==='import-data'}
                    onClick={() => dataRef.current?.click()} />
                  <input ref={dataRef} type="file" accept=".csv,.xlsx,.xls" style={{ display:'none' }} onChange={handleImportData} />

                  <ActionButton label="Simulate Live Feed"
                    icon={<Play size={13}/>} loading={actionLoading==='simulate'}
                    onClick={() => simRef.current?.click()}
                    style={{ borderColor:'var(--accent)', color:'var(--accent)' }} />
                  <input ref={simRef} type="file" accept=".csv,.xlsx,.xls" style={{ display:'none' }} onChange={handleSimulate} />
                </div>

                {/* Data preview after import */}
                {dataPreview && (
                  <div style={{ marginTop:'0.75rem', padding:'8px 12px', borderRadius:6,
                    background:'var(--accent-dim)', border:'1px solid var(--accent)33', fontSize:12 }}>
                    <strong>Data imported:</strong> {dataPreview.imported} readings loaded,
                    {dataPreview.skipped > 0 ? ` ${dataPreview.skipped} skipped,` : ''}
                    {' '}from {dataPreview.total} total rows.
                    You can now click "Train on existing data" to train the model.
                  </div>
                )}
                {importMsg && (
                  <div style={{ marginTop:'0.75rem', padding:'8px 12px', borderRadius:6,
                    background:'var(--green-dim)', color:'var(--green)', fontSize:12, border:'1px solid var(--green-glow)' }}>
                    {importMsg}
                  </div>
                )}
                {simMsg && (
                  <div style={{ marginTop:'0.75rem', padding:'8px 12px', borderRadius:6,
                    background:'var(--accent-dim)', color:'var(--accent)', fontSize:12, border:'1px solid var(--accent)33' }}>
                    {simMsg}
                  </div>
                )}
                {error && (
                  <div style={{ marginTop:'0.75rem', padding:'8px 12px', borderRadius:6,
                    background:'var(--red-dim)', color:'var(--red)', fontSize:12, border:'1px solid var(--red-glow)' }}>
                    {error}
                  </div>
                )}
              </div>

              {/* Model evaluation */}
              {evaluation && (
                <div className="card" style={{ marginBottom:'1rem' }}>
                  <h3 style={{ fontSize:13, fontWeight:600, marginBottom:'0.75rem', display:'flex', alignItems:'center', gap:6 }}>
                    <CheckCircle size={14} color="var(--green)"/> Model Evaluation (16 core features)
                  </h3>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10, marginBottom:'0.75rem' }}>
                    <MetricBox label="Features" value={`${evaluation.n_features} selected`} />
                    <MetricBox label="YELLOW threshold" value={evaluation.threshold_yellow} />
                    <MetricBox label="RED threshold" value={evaluation.threshold_red} />
                  </div>
                  {evaluation.features && (
                    <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginTop:6 }}>
                      {evaluation.features.map(f => (
                        <span key={f} className="badge badge-blue" style={{ fontSize:9 }}>{f}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Baseline stats */}
              {baseline && <BaselineStats baseline={baseline} />}

              {/* Telemetry chart */}
              {telemetry.length > 0 && (
                <div className="card" style={{ marginBottom:'1rem' }}>
                  <h3 style={{ fontSize:13, fontWeight:600, marginBottom:'0.75rem' }}>
                    Collected Telemetry ({telemetry.length} readings)
                  </h3>
                  <AnomalyChart telemetry={telemetry} height={200} />
                </div>
              )}
            </>
          )}

          {!ts && sel && (
            <div style={{ textAlign:'center', padding:'2rem', color:'var(--text-muted)' }}>
              <Loader size={18} className="spin" style={{ marginBottom:8 }} /> Loading...
            </div>
          )}
        </>
      )}
    </div>
  )
}

/* Button with loading spinner */
function ActionButton({ label, icon, loading, onClick, disabled, style }) {
  return (
    <button className="btn" onClick={onClick} disabled={disabled || loading} style={style}>
      {loading ? <Loader size={13} className="spin" /> : icon}
      {loading ? `${label}...` : label}
    </button>
  )
}

function MetricBox({ label, value }) {
  return (
    <div style={{ padding:'8px 10px', borderRadius:6, background:'var(--bg-raised)', border:'1px solid var(--border)' }}>
      <div style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:3 }}>{label}</div>
      <div className="mono" style={{ fontSize:13, color:'var(--accent)', fontWeight:500 }}>{value}</div>
    </div>
  )
}

function PhaseDisplay({ status }) {
  const { phase, progress_pct, sample_count, target_samples, trained_at, baseline_features } = status
  if (phase === 'training') return (
    <div style={{ display:'flex', alignItems:'center', gap:10, color:'var(--accent)' }}>
      <Loader size={16} className="spin" />
      <div><div style={{ fontWeight:600 }}>Training on 16 core features...</div>
      <div style={{ fontSize:11, color:'var(--text-muted)' }}>~30–60 seconds. Updating automatically.</div></div>
    </div>
  )
  if (phase === 'learning') return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.75rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:'var(--yellow)', animation:'pulse-ring 2s ease-out infinite' }}/>
          <span style={{ fontWeight:600, color:'var(--yellow)' }}>Learning Phase Active</span>
        </div>
        <span className="mono" style={{ fontSize:12, color:'var(--text-muted)' }}>{sample_count} / {target_samples}</span>
      </div>
      <div style={{ height:6, background:'var(--bg-overlay)', borderRadius:3, overflow:'hidden', marginBottom:6 }}>
        <div style={{ height:'100%', borderRadius:3, width:`${progress_pct}%`, background:'var(--yellow)', transition:'width 0.5s ease' }}/>
      </div>
    </div>
  )
  if (phase === 'monitoring') return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8 }}>
        <CheckCircle size={16} color="var(--green)"/>
        <span style={{ fontWeight:600, color:'var(--green)' }}>Models Trained — Monitoring Active</span>
      </div>
      <div style={{ fontSize:12, color:'var(--text-muted)', marginBottom:8 }}>
        {sample_count} samples · {trained_at ? new Date(trained_at).toLocaleString() : ''}
      </div>
      {baseline_features?.length > 0 && (
        <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
          {baseline_features.map(f => (
            <span key={f} className="badge badge-blue" style={{ fontSize:9 }}>{f}</span>
          ))}
        </div>
      )}
    </div>
  )
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, color:'var(--text-muted)', fontSize:13 }}>
      <Clock size={14}/> No training started yet.
    </div>
  )
}

function BaselineStats({ baseline }) {
  return (
    <div className="card" style={{ marginBottom:'1rem' }}>
      <h3 style={{ fontSize:13, fontWeight:600, marginBottom:'0.75rem', display:'flex', alignItems:'center', gap:6 }}>
        <BarChart2 size={14} color="var(--accent)"/> Baseline Statistics (16 core features)
      </h3>
      <div style={{ overflowX:'auto' }}>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
          <thead>
            <tr>{['Feature','Mean','Std Dev','Min','Max','P5','P95'].map(h => (
              <th key={h} style={{ padding:'6px 10px', textAlign:'left', color:'var(--text-muted)',
                fontWeight:500, borderBottom:'1px solid var(--border)', fontSize:10,
                textTransform:'uppercase', letterSpacing:'0.05em' }}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {Object.entries(baseline).map(([feat, s], i) => (
              <tr key={feat} style={{ background: i%2===0?'transparent':'var(--bg-raised)' }}>
                <td style={{ padding:'6px 10px', fontFamily:'var(--font-mono)', color:'var(--accent)', fontWeight:500 }}>{feat}</td>
                {['mean','std','min','max','p5','p95'].map(k => (
                  <td key={k} className="mono" style={{ padding:'6px 10px', color:'var(--text-secondary)', fontSize:11 }}>
                    {typeof s[k]==='number' ? s[k].toFixed(3) : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
