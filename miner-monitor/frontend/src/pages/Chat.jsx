import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Bot, User, AlertTriangle, CheckCircle, Cpu, RefreshCw, Loader } from 'lucide-react'
import { api, streamChat } from '../utils/api.js'
import { useMiners } from '../hooks/useMiners.js'
import StatusBadge from '../components/StatusBadge.jsx'

const SUGGESTED_QUESTIONS = [
  'Why is this miner in a yellow state?',
  'What do the hardware error counts mean?',
  'How do I interpret the anomaly score?',
  'What maintenance steps should I take?',
  'What is a normal rejection rate?',
  'How do fan speeds affect temperature?',
  'Why might hashrate drop suddenly?',
]

export default function Chat() {
  const { minerId: paramMinerId } = useParams()
  const navigate = useNavigate()
  const { miners } = useMiners()

  const [selectedMiner, setSelectedMiner] = useState(paramMinerId || '')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [minerStatus, setMinerStatus] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Sync route param → state
  useEffect(() => {
    if (paramMinerId) setSelectedMiner(paramMinerId)
  }, [paramMinerId])

  // Auto-select first miner if none
  useEffect(() => {
    if (!selectedMiner && miners.length > 0) {
      setSelectedMiner(miners[0].id)
    }
  }, [miners, selectedMiner])

  // Load Ollama status once
  useEffect(() => {
    api.chat.status().then(setOllamaStatus).catch(() => {})
  }, [])

  // Load chat history + miner status when miner changes
  useEffect(() => {
    if (!selectedMiner) return
    setMessages([])

    // Load history
    api.chat.history(selectedMiner)
      .then(hist => {
        if (hist.length > 0) {
          setMessages(hist.map(m => ({ role: m.role, content: m.content })))
        } else {
          // Welcome message
          setMessages([{
            role: 'assistant',
            content: `Hello! I'm your mining hardware diagnostics assistant. I have access to real-time telemetry and anomaly data for this miner.\n\nAsk me anything — I can explain the current status, diagnose issues, or walk you through troubleshooting steps.`,
          }])
        }
      })
      .catch(() => {})

    // Load miner status for context panel
    api.miners.status(selectedMiner).then(setMinerStatus).catch(() => {})
  }, [selectedMiner])

  const sendMessage = useCallback(async (text) => {
    const content = (text || input).trim()
    if (!content || streaming) return
    setInput('')

    const userMsg = { role: 'user', content }
    const history = messages.filter(m => m.role !== 'system')

    setMessages(prev => [...prev, userMsg])
    setStreaming(true)

    // Start with an empty assistant message that gets filled token by token
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      await streamChat(
        { message: content, miner_id: selectedMiner || null, history },
        (token) => {
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.streaming) {
              updated[updated.length - 1] = { ...last, content: last.content + token }
            }
            return updated
          })
        },
        () => {
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.streaming) {
              updated[updated.length - 1] = { ...last, streaming: false }
            }
            return updated
          })
          setStreaming(false)
          inputRef.current?.focus()
        }
      )
    } catch (e) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `Error: ${e.message}. Make sure Ollama is running (ollama serve).`,
          streaming: false,
        }
        return updated
      })
      setStreaming(false)
    }
  }, [input, messages, streaming, selectedMiner])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

      {/* Left panel: miner selector + context */}
      <div style={{
        width: 260, flexShrink: 0,
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg-surface)',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Context
          </div>
          <label>Active miner</label>
          <select
            value={selectedMiner}
            onChange={e => {
              setSelectedMiner(e.target.value)
              navigate(e.target.value ? `/chat/${e.target.value}` : '/chat')
            }}
            style={{ marginTop: 5 }}
          >
            <option value="">General (no miner)</option>
            {miners.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        {/* Miner status snapshot */}
        {minerStatus && (
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Current status</span>
              <StatusBadge status={minerStatus.status} />
            </div>
            {minerStatus.current_values && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {Object.entries(minerStatus.current_values).slice(0, 5).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 130 }}>{k}</span>
                    <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      {typeof v === 'number' ? v.toFixed(2) : v}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {minerStatus.rule_violations?.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {minerStatus.rule_violations.slice(0, 2).map((v, i) => (
                  <div key={i} style={{
                    fontSize: 10, padding: '3px 6px', borderRadius: 4, marginBottom: 3,
                    background: v.severity === 'red' ? 'var(--red-dim)' : 'var(--yellow-dim)',
                    color: v.severity === 'red' ? 'var(--red)' : 'var(--yellow)',
                  }}>
                    {v.rule_name}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Gemini AI Status */}
        {ollamaStatus && (
          <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 11,
              color: ollamaStatus.api_key_set ? 'var(--green)' : 'var(--yellow)',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: ollamaStatus.api_key_set ? 'var(--green)' : 'var(--yellow)',
              }} />
              {ollamaStatus.api_key_set
                ? `Gemini 2.0 Flash · Ready`
                : 'Gemini API key not set'}
            </div>
            {!ollamaStatus.api_key_set && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.8 }}>
                <strong style={{ color: 'var(--accent)' }}>Setup (free, 2 minutes):</strong><br/>
                1. Go to <a href="https://aistudio.google.com/apikey" target="_blank"
                  style={{ color: 'var(--accent)' }}>aistudio.google.com/apikey</a><br/>
                2. Sign in with Google → Create API Key<br/>
                3. Set before starting server: <span className="mono">set GEMINI_API_KEY=your_key</span><br/>
                4. Or save to file: <span className="mono">backend/data/gemini_key.txt</span><br/>
                5. Restart the backend server
              </div>
            )}
          </div>
        )}

        {/* Suggested questions */}
        <div style={{ padding: '1rem 1.25rem', flex: 1, overflowY: 'auto' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Suggested questions
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                disabled={streaming}
                style={{
                  background: 'var(--bg-raised)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '6px 10px', cursor: 'pointer',
                  fontSize: 11, color: 'var(--text-secondary)', textAlign: 'left',
                  transition: 'var(--transition)', lineHeight: 1.4,
                }}
                onMouseEnter={e => { e.target.style.borderColor = 'var(--accent)'; e.target.style.color = 'var(--accent)' }}
                onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-secondary)' }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel: chat */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Chat header */}
        <div style={{
          padding: '1rem 1.5rem',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'var(--bg-surface)',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'var(--accent-dim)', border: '1px solid var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bot size={16} color="var(--accent)" />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Mining Diagnostics Assistant</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {selectedMiner
                ? `Context: ${miners.find(m => m.id === selectedMiner)?.name || selectedMiner}`
                : 'No miner selected — general mode'}
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            {selectedMiner && (
              <button
                className="btn btn-sm"
                onClick={() => api.miners.status(selectedMiner).then(setMinerStatus)}
                data-tooltip="Refresh miner context"
              >
                <RefreshCw size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((msg, i) => (
            <ChatBubble key={i} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-surface)',
        }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={streaming ? 'Responding...' : 'Ask about your miner... (Enter to send, Shift+Enter for newline)'}
              disabled={streaming}
              rows={2}
              style={{
                flex: 1, resize: 'none', minHeight: 44,
                fontFamily: 'var(--font-ui)', lineHeight: 1.5,
              }}
            />
            <button
              className="btn btn-primary"
              onClick={() => sendMessage()}
              disabled={streaming || !input.trim()}
              style={{ padding: '10px 16px', flexShrink: 0, alignSelf: 'flex-end' }}
            >
              {streaming
                ? <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
                : <Send size={14} />}
            </button>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            Powered by Gemini 2.0 Flash (Google AI) · Free API key needed
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Chat bubble ─────────────────────────────────────────────────────────────

function ChatBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div style={{
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      alignItems: 'flex-start',
      gap: 10,
    }}>
      {/* Avatar */}
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: isUser ? 'var(--blue-dim)' : 'var(--accent-dim)',
        border: `1px solid ${isUser ? '#3b82f633' : 'var(--accent)'}`,
      }}>
        {isUser
          ? <User size={14} color="var(--blue)" />
          : <Bot size={14} color="var(--accent)" />}
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth: '75%',
        padding: '10px 14px',
        borderRadius: isUser ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
        background: isUser ? 'var(--bg-overlay)' : 'var(--bg-raised)',
        border: `1px solid ${isUser ? 'var(--border-bright)' : 'var(--border)'}`,
        fontSize: 13, lineHeight: 1.65,
        color: 'var(--text-primary)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {message.content}
        {message.streaming && (
          <span style={{
            display: 'inline-block', width: 2, height: 14,
            background: 'var(--accent)', marginLeft: 2, verticalAlign: 'middle',
            animation: 'pulse-ring 1s ease-out infinite',
          }} />
        )}
      </div>
    </div>
  )
}
