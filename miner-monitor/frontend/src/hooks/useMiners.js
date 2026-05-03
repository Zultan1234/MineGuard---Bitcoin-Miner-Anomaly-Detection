import { useState, useEffect, useCallback } from 'react'
import { api } from '../utils/api.js'
import { useLiveSocket } from './useLiveSocket.js'

// Module-level state so all components share one source of truth
let _miners = []
const _listeners = new Set()

function notify() {
  _listeners.forEach(fn => fn([..._miners]))
}

export function useMiners() {
  const [miners, setMiners] = useState(_miners)

  useEffect(() => {
    _listeners.add(setMiners)
    return () => _listeners.delete(setMiners)
  }, [])

  // Live WS updates — patch status without re-fetching
  const onMessage = useCallback((msg) => {
    if (msg.type !== 'telemetry') return
    _miners = _miners.map(m =>
      m.id === msg.miner_id
        ? { ...m, status: msg.status, lastValues: msg.values, lastSeen: msg.timestamp }
        : m
    )
    notify()
  }, [])

  useLiveSocket(onMessage)

  const refresh = useCallback(async () => {
    try {
      const list = await api.miners.list()
      // Fetch status for each miner in parallel
      const withStatus = await Promise.all(
        list.map(async (m) => {
          try {
            const s = await api.miners.status(m.id)
            return { ...m, status: s.status, lastValues: s.current_values, lastSeen: s.timestamp }
          } catch {
            return { ...m, status: 'UNKNOWN' }
          }
        })
      )
      _miners = withStatus
      notify()
    } catch (e) {
      console.error('Failed to fetch miners:', e)
    }
  }, [])

  // Auto-fetch on mount
  useEffect(() => { refresh() }, [refresh])

  return { miners, refresh }
}
