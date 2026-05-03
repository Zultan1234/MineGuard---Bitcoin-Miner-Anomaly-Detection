const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
    body: options.body instanceof FormData
      ? options.body
      : options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  miners: {
    list:      ()               => request('/miners/'),
    add:       (body)           => request('/miners/', { method:'POST', body }),
    get:       (id)             => request(`/miners/${id}`),
    update:    (id, body)       => request(`/miners/${id}`, { method:'PATCH', body }),
    delete:    (id)             => request(`/miners/${id}`, { method:'DELETE' }),
    poll:      (id)             => request(`/miners/${id}/poll`, { method:'POST' }),
    status:    (id)             => request(`/miners/${id}/status`),
    telemetry: (id, limit=100)  => request(`/miners/${id}/telemetry?limit=${limit}`),
    discover:  (ip, port=4028)  => request('/miners/discover', { method:'POST', body:{ip,port} }),
  },
  training: {
    start:       (id, body)  => request(`/training/${id}/start`, { method:'POST', body }),
    status:      (id)        => request(`/training/${id}/status`),
    trainNow:    (id)        => request(`/training/${id}/train-now`, { method:'POST' }),
    baseline:    (id)        => request(`/training/${id}/baseline`),
    evaluate:    (id)        => request(`/training/${id}/evaluate`),
    edaReport:   (id)        => request(`/training/${id}/eda-report`),
    exportModel: (id)        => { window.open(`${BASE}/training/${id}/export`, '_blank') },
    exportData:  (id, fmt)   => { window.open(`${BASE}/training/${id}/export-data?fmt=${fmt}`, '_blank') },
    importData:  (id, file)  => {
      const fd = new FormData(); fd.append('file', file)
      return request(`/training/${id}/import-data`, { method:'POST', body:fd })
    },
    importModel: (id, file)  => {
      const fd = new FormData(); fd.append('file', file)
      return request(`/training/${id}/import-model`, { method:'POST', body:fd })
    },
    simulate:    (id, file)  => {
      const fd = new FormData(); fd.append('file', file)
      return request(`/training/${id}/simulate`, { method:'POST', body:fd })
    },
  },
  anomaly: {
    events: (id, limit=50) => request(`/anomaly/${id}/events?limit=${limit}`),
    latest: (id)           => request(`/anomaly/${id}/latest`),
    all:    ()             => request('/anomaly/summary/all'),
  },
  chat: {
    send:    (body) => request('/chat/message', { method:'POST', body }),
    history: (id)   => request(`/chat/history/${id}`),
    status:  ()     => request('/chat/status'),
  },
  presets: {
    list: ()     => request('/presets/'),
    get:  (id)   => request(`/presets/${id}`),
    save: (body) => request('/presets/', { method:'POST', body }),
  },
}

export async function streamChat(body, onToken, onDone) {
  const res = await fetch(`${BASE}/chat/stream`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body),
  })
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6)
        if (token === '[DONE]') { onDone?.(); return }
        onToken(token)
      }
    }
  }
  onDone?.()
}
