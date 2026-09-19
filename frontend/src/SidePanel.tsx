import { CheckCircle, CircleDashed, CircleHalf, ShieldWarning } from '@phosphor-icons/react'
import { isLive, nextAsk } from './script'
import type { ConsoleApi } from './useConsole'
import type { CallState, JourneyDefinition } from './types'
import { Badge, Panel } from './ui'

function ScriptCard({ call, journey }: { call: CallState; journey: JourneyDefinition }) {
  const ask = nextAsk(call, journey)
  if (call.status === 'completed') {
    return (
      <Panel title="Script">
        <p className="text-sm text-emerald-300">Journey complete. Closing script delivered.</p>
      </Panel>
    )
  }
  if (!ask) return null
  const { field, section } = ask
  return (
    <Panel title="Ava is asking now" right={<Badge tone="blue">{section.title}</Badge>}>
      <p className="text-xs text-zinc-500">
        {field.label}
        {field.required ? '' : ' (optional)'}
      </p>
      <p className="mt-2 text-[17px] leading-snug tracking-tight text-zinc-100">{ask.isRetry ? field.reprompt : field.script}</p>
      {ask.onFile && !field.sensitive && (
        <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-200 ring-1 ring-inset ring-amber-400/20">On file: {ask.onFile}. Confirm it, do not re-ask.</p>
      )}
      <p className="mt-3 text-xs leading-relaxed text-zinc-500">{field.ask_hint}</p>
      {ask.isRetry && <p className="mt-2 text-xs text-red-300">Re-ask {call.failures[field.id]} of 3. A third failure hands off to a human.</p>}
    </Panel>
  )
}

function Progress({ call, journey }: { call: CallState; journey: JourneyDefinition }) {
  const current = nextAsk(call, journey)?.field.id
  const required = journey.sections.flatMap((s) => s.fields.filter((f) => f.required))
  const capturedReq = required.filter((f) => call.sources[f.id] === 'voice').length
  const pct = Math.round((capturedReq / required.length) * 100)

  return (
    <Panel title="Journey" right={<span className="font-mono text-xs tabular-nums text-zinc-400">{capturedReq}/{required.length} required</span>}>
      <div className="mb-5 h-1 overflow-hidden rounded-lg bg-raised">
        <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="flex flex-col gap-5">
        {journey.sections.map((s) => (
          <div key={s.id}>
            <p className={`mb-2 text-xs font-medium ${s.id === call.resume_section ? 'text-accent' : 'text-zinc-400'}`}>
              {s.title}
              {s.id === call.resume_section && <span className="ml-2 font-normal text-zinc-500">resumed here</span>}
            </p>
            <ul className="flex flex-col">
              {s.fields.map((f) => {
                const src = call.sources[f.id]
                const val = call.fields[f.id]
                const isCurrent = f.id === current && isLive(call)
                const Ico = src === 'voice' ? CheckCircle : src === 'prefilled' ? CircleHalf : CircleDashed
                return (
                  <li key={f.id} className={`flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-[13px] ${isCurrent ? 'bg-accent/10 ring-1 ring-inset ring-accent/30' : ''}`}>
                    <span className="flex items-center gap-2">
                      <Ico size={15} weight={src === 'voice' ? 'fill' : 'regular'} className={src === 'voice' ? 'text-emerald-400' : src === 'prefilled' ? 'text-amber-400' : 'text-zinc-700'} />
                      <span className={src ? 'text-zinc-200' : 'text-zinc-500'}>{f.label}</span>
                    </span>
                    <span className={`max-w-[50%] truncate ${src === 'voice' ? 'text-emerald-300' : src === 'prefilled' ? 'text-amber-300/80' : 'text-zinc-700'}`}>
                      {val ? (f.sensitive ? 'Preference only' : val) : '-'}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-zinc-600">Filled: captured by voice. Half: on file, awaiting confirmation. Empty: pending.</p>
    </Panel>
  )
}

function Handoff({ call, journey, c }: { call: CallState; journey: JourneyDefinition; c: ConsoleApi }) {
  const esc = call.escalation
  if (!esc) return null
  const first = call.lead_name?.split(' ')[0] ?? 'there'
  const opening = journey.handoff_script.replace('{first_name}', first).replace('{agent_name}', journey.agent_name)
  const captured = Object.keys(call.fields).filter((k) => call.sources[k] === 'voice').length
  return (
    <div className="rounded-lg border border-amber-400/30 bg-amber-500/[0.06] p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold capitalize text-amber-200">Warm handoff: {esc.category.replace(/_/g, ' ')}</p>
        {esc.auto && <Badge tone="amber">Safety net</Badge>}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-amber-100/90">{esc.reason}</p>
      <div className="mt-4 border-t border-amber-400/15 pt-4">
        <p className="text-xs text-zinc-500">Briefing for {journey.agent_name}</p>
        <p className="mt-1.5 text-sm leading-relaxed text-zinc-200">{esc.summary_for_human}</p>
        <p className="mt-2 text-xs text-zinc-500">{captured} fields already captured. The customer does not repeat anything.</p>
      </div>
      <div className="mt-4 border-t border-amber-400/15 pt-4">
        <p className="text-xs text-zinc-500">Say when you pick up</p>
        <p className="mt-1.5 text-sm italic leading-relaxed text-zinc-200">"{opening}"</p>
      </div>
      {call.signals.some((s) => s.type === 'card_data') && (
        <p className="mt-4 flex items-start gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-200 ring-1 ring-inset ring-red-400/20">
          <ShieldWarning size={15} className="mt-px shrink-0" />
          Card data boundary held. The number was redacted from the transcript and never stored.
        </p>
      )}
      {call.human_joined_at ? (
        <p className="mt-4 text-sm font-medium text-emerald-300">Transfer requested to {journey.agent_name}</p>
      ) : (
        <button onClick={() => c.takeOver(call.call_id)} className="mt-4 w-full rounded-lg bg-amber-300 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-amber-200">
          Take over this call
        </button>
      )}
    </div>
  )
}

export default function SidePanel({ c }: { c: ConsoleApi }) {
  const call = c.selected
  const journey = c.journey
  if (!journey) {
    return (
      <Panel title="Journey">
        <div className="flex flex-col gap-3" aria-label="Loading journey">
          {[80, 60, 70, 50].map((w) => (
            <div key={w} className="h-4 animate-pulse rounded-lg bg-raised" style={{ width: `${w}%` }} />
          ))}
        </div>
      </Panel>
    )
  }
  if (!call) {
    return (
      <Panel title="Guardrails">
        <ul className="flex flex-col gap-3 text-[13px] leading-relaxed text-zinc-400">
          {journey.guardrails.map((g) => (
            <li key={g} className="flex gap-3">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
              {g}
            </li>
          ))}
        </ul>
      </Panel>
    )
  }
  return (
    <div className="flex flex-col gap-6">
      <Handoff call={call} journey={journey} c={c} />
      {call.status === 'completed' && call.submission && (
        <div className="rounded-lg border border-emerald-400/25 bg-emerald-500/[0.06] p-5">
          <p className="text-sm font-semibold text-emerald-200">Submitted to journey sandbox</p>
          <p className="mt-1 font-mono text-lg text-emerald-100">{call.submission.reference}</p>
          <p className="mt-1 text-xs text-emerald-300/70">All required fields were validated server-side before submit.</p>
        </div>
      )}
      {call.status === 'callback' && (
        <div className="rounded-lg border border-line bg-surface p-5 text-sm text-zinc-200">
          Callback requested: <span className="font-semibold">{call.callback_time ?? 'time not given'}</span>
        </div>
      )}
      {call.status === 'declined' && (
        <div className="rounded-lg border border-red-400/20 bg-red-500/[0.06] p-5 text-sm leading-relaxed text-red-100">
          Customer declined. Thanked, logged and added to the suppression list. No second attempt.
        </div>
      )}
      {isLive(call) && <ScriptCard call={call} journey={journey} />}
      <Progress call={call} journey={journey} />
    </div>
  )
}
