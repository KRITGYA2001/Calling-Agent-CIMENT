import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_BASE, api } from './api'
import type { CallState, JourneyDefinition, Lead, Metrics } from './types'

const ACTIVE = new Set(['dialling', 'in_progress'])

export function useConsole() {
  const [journey, setJourney] = useState<JourneyDefinition | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [calls, setCalls] = useState<Record<string, CallState>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pinned, setPinned] = useState(false) // user picked a call manually -> stop auto-following
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshLeads = useCallback(() => api<Lead[]>('/leads').then(setLeads).catch(() => {}), [])
  const refreshMetrics = useCallback(() => api<Metrics>('/metrics').then(setMetrics).catch(() => {}), [])

  // Initial load
  useEffect(() => {
    api<JourneyDefinition>('/journey').then(setJourney).catch(() => setError('Cannot reach the backend. Is it running?'))
    api<CallState[]>('/calls')
      .then((list) => setCalls(Object.fromEntries(list.map((c) => [c.call_id, c]))))
      .catch(() => {})
    refreshLeads()
    refreshMetrics()
  }, [refreshLeads, refreshMetrics])

  // One live feed for every call
  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/vapi/stream`)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = (evt) => {
      const call = JSON.parse(evt.data) as CallState
      setCalls((prev) => ({ ...prev, [call.call_id]: call }))
      refreshLeads()
      refreshMetrics()
    }
    return () => source.close()
  }, [refreshLeads, refreshMetrics])

  const sorted = useMemo(() => Object.values(calls).sort((a, b) => b.started_at - a.started_at), [calls])

  // Auto-follow the newest active call unless the user pinned another one
  useEffect(() => {
    if (pinned) return
    const live = sorted.find((c) => ACTIVE.has(c.status) || c.status === 'escalated')
    const next = live ?? sorted[0]
    if (next && next.call_id !== selectedId) setSelectedId(next.call_id)
  }, [sorted, pinned, selectedId])

  const select = useCallback((id: string) => {
    setPinned(true)
    setSelectedId(id)
  }, [])

  const follow = useCallback(() => setPinned(false), [])

  async function guarded<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setError(null)
    setBusy(label)
    try {
      return await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const dialLead = (leadId: string) =>
    guarded(`dial-${leadId}`, async () => {
      const res = await api<{ call_id: string }>(`/leads/${leadId}/call`, { method: 'POST' })
      setPinned(false)
      setSelectedId(res.call_id)
      refreshLeads()
    })

  const runQueue = () =>
    guarded('queue', async () => {
      const res = await api<{ call_id: string }>('/queue/run', { method: 'POST' })
      setPinned(false)
      setSelectedId(res.call_id)
      refreshLeads()
    })

  const endCall = (call: CallState) => guarded('end', () => api(`/calls/${call.call_id}/end`, { method: 'POST' }))

  const takeOver = (callId: string) => guarded('takeover', () => api(`/calls/${callId}/take-over`, { method: 'POST' }))

  return {
    journey,
    leads,
    metrics,
    calls: sorted,
    selected: selectedId ? (calls[selectedId] ?? null) : null,
    selectedId,
    pinned,
    connected,
    busy,
    error,
    setError,
    select,
    follow,
    dialLead,
    runQueue,
    endCall,
    takeOver,
  }
}

export type ConsoleApi = ReturnType<typeof useConsole>
