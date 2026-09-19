import { fmtDuration } from './script'
import type { Metrics } from './types'

function Stat({ label, value, sub, tone = 'text-zinc-100' }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="min-w-0 px-5 py-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-medium tabular-nums tracking-tight ${tone}`}>{value}</p>
      {sub && <p className="mt-0.5 truncate text-xs text-zinc-500">{sub}</p>}
    </div>
  )
}

export default function MetricsBar({ metrics }: { metrics: Metrics | null }) {
  const m = metrics
  const pct = (v: number | null | undefined) => (v == null ? '-' : `${Math.round(v * 100)}%`)
  return (
    <div>
      <div className="grid grid-cols-2 divide-x divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface sm:grid-cols-4 lg:grid-cols-7 lg:divide-y-0">
        <Stat label="Calls placed" value={String(m?.calls_total ?? 0)} sub={m?.dnc_blocked ? `${m.dnc_blocked} blocked by DNC` : 'DNC gate active'} />
        <Stat label="Completed" value={String(m?.completed ?? 0)} sub={`${pct(m?.completion_rate)} completion`} tone="text-emerald-300" />
        <Stat label="Handed to human" value={String(m?.escalated ?? 0)} sub={`${m?.declined ?? 0} declined, ${m?.callbacks ?? 0} callbacks`} tone="text-amber-300" />
        <Stat
          label="Avg completed call"
          value={fmtDuration(m?.avg_completed_call_seconds)}
          sub={m?.manual_estimate_seconds_per_journey ? `manual est. ${fmtDuration(m.manual_estimate_seconds_per_journey)}` : 'vs manual estimate'}
        />
        <Stat label="Fields by voice" value={String(m?.fields_captured_by_voice ?? 0)} sub="no typing needed" />
        <Stat label="Bad values caught" value={String(m?.validation_errors_caught ?? 0)} sub="checked before submit" tone="text-accent" />
        <Stat label="Human time avoided" value={`${m?.human_minutes_avoided ?? 0} min`} sub="vs manual workflow*" tone="text-emerald-300" />
      </div>
      <p className="mt-2 text-xs text-zinc-600">* {m?.baseline_note ?? 'Manual baseline is an assumption until measured.'}</p>
    </div>
  )
}
