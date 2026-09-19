import { PhoneCall } from '@phosphor-icons/react'
import CallPanel from './CallPanel'
import LeadQueue from './LeadQueue'
import MetricsBar from './MetricsBar'
import SidePanel from './SidePanel'
import { useConsole } from './useConsole'
import { Badge } from './ui'

function App() {
  const c = useConsole()

  return (
    <div className="min-h-[100dvh] bg-ink text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-line bg-ink/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1500px] items-center justify-between gap-4 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-ink">
              <PhoneCall size={18} weight="fill" />
            </div>
            <div className="leading-tight">
              <h1 className="text-[15px] font-semibold tracking-tight">Ava</h1>
              <p className="hidden text-xs text-zinc-500 sm:block">Energy journey recovery, voice-led</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-xs text-zinc-500 md:inline">Agent-driven mode</span>
            <Badge tone="neutral">Test data only</Badge>
            <Badge tone={c.connected ? 'green' : 'red'} pulse={c.connected}>
              {c.connected ? 'Live' : 'Offline'}
            </Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1500px] flex-col gap-6 px-6 py-6">
        {c.error && (
          <div className="flex items-start justify-between gap-3 rounded-lg border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <span>{c.error}</span>
            <button onClick={() => c.setError(null)} className="text-red-300 hover:text-red-100">
              Dismiss
            </button>
          </div>
        )}

        <MetricsBar metrics={c.metrics} />

        <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)_380px]">
          <LeadQueue c={c} />
          <CallPanel c={c} />
          <SidePanel c={c} />
        </div>

        {c.calls.length > 1 && (
          <section>
            <h2 className="mb-3 text-sm font-semibold tracking-tight">Call history</h2>
            <div className="flex flex-wrap gap-2">
              {c.calls.map((call) => (
                <button
                  key={call.call_id}
                  onClick={() => c.select(call.call_id)}
                  className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${call.call_id === c.selectedId ? 'border-accent/50 bg-accent/10 text-zinc-100' : 'border-line text-zinc-400 hover:bg-raised'}`}
                >
                  {call.lead_name ?? 'Unknown'}, {call.status.replace('_', ' ')}
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
