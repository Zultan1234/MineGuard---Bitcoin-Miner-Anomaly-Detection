import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plug, CheckCircle, AlertTriangle, X } from 'lucide-react'
import { api } from '../utils/api.js'

const STEPS = ['Connect', 'Configure', 'Done']

export default function Setup() {
  const navigate = useNavigate()
  const [step, setStep]               = useState(0)
  const [ip, setIp]                   = useState('')
  const [port, setPort]               = useState('5050')
  const [connecting, setConnecting]   = useState(false)
  const [connectError, setConnectError] = useState('')
  const [discovered, setDiscovered]   = useState(null)
  const [connectionMode, setMode]     = useState('')
  const [minerId, setMinerId]         = useState('')
  const [minerName, setMinerName]     = useState('')
  const [pollInterval, setPollInterval] = useState('30')
  const [saving, setSaving]           = useState(false)
  const [saveError, setSaveError]     = useState('')

  async function handleDiscover() {
    if (!ip.trim()) return
    setConnecting(true); setConnectError(''); setDiscovered(null)
    try {
      const result = await api.miners.discover(ip.trim(), parseInt(port))
      const count = Object.keys(result.numeric_fields || {}).length
      if (count === 0) {
        setConnectError(
          `Connected but got 0 numeric fields. ` +
          `If using bridge.py: open http://${ip.trim()}:${port}/fields to test. ` +
          `If direct TCP: cgminer api-allow may be blocking access.`)
        return
      }
      setDiscovered(result)
      setMode(result.mode || '')
      setMinerName(`Miner-${ip.trim().split('.').pop()}`)
      setMinerId(`miner-${ip.trim().replace(/\./g,'-')}`)
      setStep(1)
    } catch (e) { setConnectError(e.message) }
    finally { setConnecting(false) }
  }

  async function handleSave() {
    if (!minerId.trim() || !minerName.trim()) { setSaveError('ID and name required'); return }
    setSaving(true); setSaveError('')
    try {
      // Save a preset with ALL discovered fields — the auto-EDA in the training
      // pipeline will automatically select the right ones when user trains.
      const allFields = Object.keys(discovered?.numeric_fields || {})
      const presetId = `auto_${minerId.trim()}`
      await api.presets.save({
        id: presetId, name: minerName,
        description: `${minerName} — auto-selected features`,
        features: allFields.map(f => ({
          raw_key: f, label: f, unit: '', warn_high: null, warn_low: null,
        })),
      })
      await api.miners.add({
        id: minerId.trim(), name: minerName.trim(),
        ip: ip.trim(), port: parseInt(port),
        preset_id: presetId, poll_interval: parseInt(pollInterval),
      })
      setStep(2)
    } catch (e) { setSaveError(e.message) }
    finally { setSaving(false) }
  }

  const fieldCount = discovered ? Object.keys(discovered.numeric_fields).length : 0

  return (
    <div style={{ padding:'1.5rem', maxWidth:640, margin:'0 auto' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:20, fontWeight:600, marginBottom:4 }}>Add Miner</h1>
        <p style={{ color:'var(--text-muted)', fontSize:13 }}>
          Connect to your miner. Features are selected automatically during training.
        </p>
      </div>

      <StepIndicator steps={STEPS} current={step} />

      <div style={{ marginTop:'2rem' }}>

        {/* STEP 0: Connect */}
        {step === 0 && (
          <div className="card">
            <h2 style={{ fontSize:15, fontWeight:600, marginBottom:4 }}>Connect to miner</h2>
            <p style={{ color:'var(--text-muted)', fontSize:12, marginBottom:'1rem' }}>
              Enter the IP of the PC running <strong>bridge.py</strong> (port 5050),
              or the miner IP directly (port 4028).
            </p>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 140px', gap:10, marginBottom:'1rem' }}>
              <div>
                <label>IP Address</label>
                <input placeholder="192.168.1.50" value={ip}
                  onChange={e => setIp(e.target.value)}
                  onKeyDown={e => e.key==='Enter' && handleDiscover()} />
              </div>
              <div>
                <label>Port</label>
                <input value={port} type="number" onChange={e => setPort(e.target.value)} />
              </div>
            </div>
            {connectError && <ErrorBox message={connectError} onDismiss={() => setConnectError('')} />}
            <button className="btn btn-primary" onClick={handleDiscover}
              disabled={connecting || !ip.trim()}
              style={{ width:'100%', justifyContent:'center', padding:'10px' }}>
              {connecting
                ? <><span className="spinner" style={{ width:14, height:14, borderWidth:2 }}/> Connecting...</>
                : <><Plug size={14}/> Connect & Discover Fields</>}
            </button>
          </div>
        )}

        {/* STEP 1: Configure */}
        {step === 1 && discovered && (
          <div className="card">
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1rem' }}>
              <div>
                <h2 style={{ fontSize:15, fontWeight:600, marginBottom:4 }}>Miner Connected</h2>
                <p style={{ color:'var(--text-muted)', fontSize:12 }}>
                  {fieldCount} fields discovered from <span className="mono">{ip}:{port}</span>
                  {connectionMode && (
                    <span style={{ marginLeft:8, padding:'1px 6px', borderRadius:4,
                      background:'var(--accent-dim)', color:'var(--accent)', fontSize:10 }}>
                      {connectionMode==='http_bridge'?'via bridge':'direct TCP'}
                    </span>
                  )}
                </p>
              </div>
              <CheckCircle size={20} color="var(--green)" />
            </div>

            {/* Auto-selection explanation */}
            <div style={{
              padding:'10px 12px', borderRadius:8, marginBottom:'1.25rem',
              background:'var(--bg-raised)', border:'1px solid var(--border)',
              fontSize:11, color:'var(--text-secondary)', lineHeight:1.7,
            }}>
              <strong style={{ color:'var(--accent)' }}>Feature selection is automatic.</strong>{' '}
              When you start training, the system analyzes the collected data and automatically
              selects the right features. It removes pool duplicates, cumulative counters,
              constant values, and redundant fields. Only features with real diagnostic value
              are kept (typically ~15-20 out of {fieldCount}).
            </div>

            <div style={{ display:'flex', flexDirection:'column', gap:12, marginBottom:'1.25rem' }}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
                <div>
                  <label>Miner ID (slug)</label>
                  <input placeholder="l3-01" value={minerId}
                    onChange={e => setMinerId(e.target.value.toLowerCase().replace(/[^a-z0-9\-_]/g,''))} />
                </div>
                <div>
                  <label>Display Name</label>
                  <input placeholder="Mining Rig 1" value={minerName}
                    onChange={e => setMinerName(e.target.value)} />
                </div>
              </div>
              <div>
                <label>Poll Interval</label>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:6 }}>
                  {['15','30','60','120'].map(v => (
                    <button key={v} className={`btn ${pollInterval===v?'btn-primary':''}`}
                      onClick={() => setPollInterval(v)} style={{ justifyContent:'center' }}>
                      {v}s
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {saveError && <ErrorBox message={saveError} onDismiss={() => setSaveError('')} />}

            <div style={{ display:'flex', justifyContent:'space-between' }}>
              <button className="btn" onClick={() => setStep(0)}>← Back</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}
                style={{ padding:'8px 20px' }}>
                {saving
                  ? <><span className="spinner" style={{ width:14, height:14, borderWidth:2 }}/> Saving...</>
                  : 'Save & Start Monitoring'}
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Done */}
        {step === 2 && (
          <div className="card" style={{ textAlign:'center', padding:'2.5rem' }}>
            <div style={{
              width:56, height:56, borderRadius:'50%', background:'var(--green-dim)',
              border:'1px solid var(--green-glow)', display:'flex', alignItems:'center',
              justifyContent:'center', margin:'0 auto 1rem',
            }}>
              <CheckCircle size={26} color="var(--green)" />
            </div>
            <h2 style={{ fontSize:17, fontWeight:600, marginBottom:6 }}>Miner Added!</h2>
            <p style={{ color:'var(--text-muted)', fontSize:13, marginBottom:'1.5rem' }}>
              <span className="mono">{minerName}</span> is now being polled every {pollInterval}s.<br/>
              Go to <strong>Training</strong> to collect data and train the model.
              Features will be selected automatically.
            </p>
            <div style={{ display:'flex', gap:10, justifyContent:'center' }}>
              <button className="btn" onClick={() => navigate('/')}>Dashboard</button>
              <button className="btn btn-primary" onClick={() => navigate('/training')}>Start Training →</button>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

function StepIndicator({ steps, current }) {
  return (
    <div style={{ display:'flex', alignItems:'center' }}>
      {steps.map((s, i) => (
        <div key={s} style={{ display:'flex', alignItems:'center', flex: i < steps.length-1?1:'none' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, flexShrink:0 }}>
            <div style={{
              width:26, height:26, borderRadius:'50%',
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:11, fontWeight:600,
              background: i<current?'var(--accent)':i===current?'var(--accent-dim)':'var(--bg-raised)',
              border:`1px solid ${i<=current?'var(--accent)':'var(--border)'}`,
              color: i<current?'var(--bg-base)':i===current?'var(--accent)':'var(--text-muted)' }}>
              {i < current ? '✓' : i+1}
            </div>
            <span style={{ fontSize:12, fontWeight:i===current?500:400,
              color:i===current?'var(--text-primary)':'var(--text-muted)' }}>{s}</span>
          </div>
          {i < steps.length-1 && (
            <div style={{ flex:1, height:1, margin:'0 10px',
              background:i<current?'var(--accent)':'var(--border)' }} />
          )}
        </div>
      ))}
    </div>
  )
}

function ErrorBox({ message, onDismiss }) {
  return (
    <div style={{ display:'flex', alignItems:'flex-start', gap:8, padding:'10px 12px',
      borderRadius:8, background:'var(--red-dim)', border:'1px solid var(--red-glow)',
      marginBottom:'1rem' }}>
      <AlertTriangle size={14} color="var(--red)" style={{ flexShrink:0, marginTop:1 }} />
      <span style={{ fontSize:12, color:'var(--red)', flex:1 }}>{message}</span>
      <button onClick={onDismiss} style={{ background:'none', border:'none', cursor:'pointer', padding:0 }}>
        <X size={13} color="var(--red)" />
      </button>
    </div>
  )
}
