import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live`
const RECONNECT_DELAY = 3000

// Global subscriber store so any component can listen to live updates
const subscribers = new Set()
let socket = null
let reconnectTimer = null
let isConnected = false
const connectedListeners = new Set()

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return

  socket = new WebSocket(WS_URL)

  socket.onopen = () => {
    isConnected = true
    clearTimeout(reconnectTimer)
    connectedListeners.forEach(fn => fn(true))
  }

  socket.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'ping') return
      subscribers.forEach(fn => fn(msg))
    } catch {}
  }

  socket.onclose = () => {
    isConnected = false
    connectedListeners.forEach(fn => fn(false))
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY)
  }

  socket.onerror = () => socket.close()
}

// Kick off connection on module load
connect()

export function useLiveSocket(onMessage) {
  const [connected, setConnected] = useState(isConnected)

  useEffect(() => {
    const cb = (v) => setConnected(v)
    connectedListeners.add(cb)
    setConnected(isConnected)
    return () => connectedListeners.delete(cb)
  }, [])

  useEffect(() => {
    if (!onMessage) return
    subscribers.add(onMessage)
    return () => subscribers.delete(onMessage)
  }, [onMessage])

  return { connected }
}
