import { useEffect, useRef, useState } from 'react'
import {
  ArrowsClockwise,
  Check,
  CheckCircle,
  Database,
  FlagCheckered,
  Handshake,
  PencilSimple,
  Phone,
  Prohibit,
  Question,
  Siren,
  Warning,
  WarningCircle,
  Broadcast,
  ShieldCheck,
  UserCircle,
  X,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import { STATUS_LABEL, fmtDuration, isLive } from './script'
import type { ConsoleApi } from './useConsole'
import type { CallEvent } from './types'
import { Badge, Panel, statusTone } from './ui'

const EVENT_ICON: Record<string, { icon: Icon; tone: string }> = {
  call: { icon: Phone, tone: 'text-zinc-400' },
  lead: { icon: UserCircle, tone: 'text-zinc-400' },
  dnc: { icon: ShieldCheck, tone: 'text-emerald-400' },
  consent: { icon: CheckCircle, tone: 'text-emerald-400' },
  field: { icon: PencilSimple, tone: 'text-accent' },
  validation: { icon: Warning, tone: 'text-red-400' },
  capture_fail: { icon: ArrowsClockwise, tone: 'text-amber-400' },
  low_confidence: { icon: Question, tone: 'text-amber-400' },
  signal: { icon: Broadcast, tone: 'text-amber-400' },
  escalation: { icon: Siren, tone: 'text-amber-400' },
  handoff: { icon: Handshake, tone: 'text-amber-400' },
  guardrail: { icon: Prohibit, tone: 'text-red-400' },
  outcome: { icon: FlagCheckered, tone: 'text-zinc-300' },
  submit: { icon: Database, tone: 'text-emerald-400' },
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function Transcript({ lines }: { lines: { role: string; text: string; ts: number }[] }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [lines.length])
  // Vapi streams one utterance in several chunks; show consecutive same-speaker chunks as one message
  const merged = lines.reduce<typeof lines>((acc, l) => {
    const last = acc[acc.length - 1]
    if (last && last.role === l.role && l.ts - last.ts < 8) acc[acc.length - 1] = { ...last, text: `${last.text} ${l.text}`, ts: l.ts }
    else acc.push({ ...l })
    return acc
  }, [])
  if (!lines.length) return <p className="py-12 text-center text-sm text-zinc-500">Waiting for the conversation to start.</p>
  return (
    <div className="flex max-h-[380px] flex-col gap-3 overflow-y-auto pr-1">
      {merged.map((l, i) => {
        const ava = l.role === 'assistant' || l.role === 'bot'
        return (
          <div key={i} className={`flex ${ava ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[82%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${ava ? 'bg-accent/10 text-zinc-100 ring-1 ring-inset ring-accent/20' : 'bg-raised text-zinc-100'}`}>
              <p className="mb-1 text-[11px] text-zinc-500">
                {ava ? 'Ava' : 'Customer'} at {clock(l.ts)}
              </p>
              {l.text}
            </div>
          </div>
        )
      })}
      <div ref={end} />
    </div>
  )
}

function Activity({ events }: { events: CallEvent[] }) {
  if (!events.length) return <p className="text-sm text-zinc-500">No activity yet.</p>
  return (
    <ol className="flex max-h-[260px] flex-col overflow-y-auto pr-1">
      {[...events].reverse().map((e, i) => {
        const meta = EVENT_ICON[e.kind]
        const Ico = meta?.icon ?? Check
        return (
          <li key={i} className="flex items-start gap-3 py-1.5 text-[13px]">
            <span className="mt-0.5 w-[68px] shrink-0 font-mono text-xs text-zinc-600">{clock(e.ts)}</span>
            <Ico size={15} className={`mt-0.5 shrink-0 ${meta?.tone ?? 'text-zinc-500'}`} />
            <span className={e.kind === 'escalation' || e.kind === 'guardrail' ? 'text-amber-200' : e.kind === 'validation' ? 'text-red-200' : 'text-zinc-300'}>{e.text}</span>
          </li>
        )
      })}
    </ol>
  )
}

export default function CallPanel({ c }: { c: ConsoleApi }) {
  const call = c.selected
  const live = call ? isLive(call) : false
  const now = useNow(live)

  if (!call) {
    return (
      <Panel title="Live call">
        <div className="flex flex-col items-center gap-2 py-20 text-center">
          <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-lg bg-raised text-zinc-400">
            <Phone size={22} />
          </div>
          <p className="text-base font-medium">No active call</p>
          <p className="max-w-sm text-sm leading-relaxed text-zinc-500">
            Choose a lead and press Call to ring their phone, or use Run next to let the queue pick. The conversation appears here as it happens.
          </p>
        </div>
      </Panel>
    )
  }

  const elapsed = (call.ended_at ?? now) - call.started_at

  return (
    <div className="flex flex-col gap-6">
      <Panel
        title="Live call"
        right={
          <div className="flex items-center gap-3">
            {c.pinned && (
              <button onClick={c.follow} className="text-xs text-accent hover:underline">
                Follow live
              </button>
            )}
            <Badge tone={statusTone(call.status)} pulse={live}>
              {STATUS_LABEL[call.status] ?? call.status}
            </Badge>
          </div>
        }
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold tracking-tight">{call.lead_name ?? 'Unknown caller'}</p>
            <p className="mt-0.5 text-xs text-zinc-500">
              {call.lead_id ?? 'No lead'}, phone call, <span className="font-mono">{call.call_id.slice(0, 8)}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono text-2xl tabular-nums tracking-tight text-zinc-100">{fmtDuration(elapsed)}</span>
            {live && (
              <button onClick={() => c.endCall(call)} className="inline-flex items-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-200 ring-1 ring-inset ring-red-400/30 transition-colors hover:bg-red-500/25">
                <X size={13} weight="bold" />
                End call
              </button>
            )}
          </div>
        </div>

        {call.dnc_check && (
          <div className="mb-4 flex flex-wrap gap-2">
            {call.dnc_check.checks.map((k) => (
              <span
                key={k.name}
                title={k.detail}
                className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] ring-1 ring-inset ${k.passed ? 'text-emerald-300 ring-emerald-400/20' : 'bg-red-500/10 text-red-300 ring-red-400/30'}`}
              >
                {k.passed ? <Check size={11} weight="bold" /> : <WarningCircle size={11} weight="bold" />}
                {k.name}
              </span>
            ))}
          </div>
        )}

        <Transcript lines={call.transcript} />

        {call.signals.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <span className="text-xs text-zinc-500">Signals</span>
            {call.signals.map((s, i) => (
              <span key={i} title={s.text} className="rounded-lg bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300 ring-1 ring-inset ring-amber-400/20">
                {s.type.replace('_', ' ')}
              </span>
            ))}
          </div>
        )}

        {(call.summary || call.recording_url) && (
          <div className="mt-4 border-t border-line pt-4 text-sm text-zinc-400">
            {call.summary && <p className="mb-1.5 leading-relaxed">{call.summary}</p>}
            {call.recording_url && (
              <a href={`https://dashboard.vapi.ai/calls/${call.call_id}`} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                Open recording in Vapi
              </a>
            )}
          </div>
        )}
      </Panel>

      <Panel title="Activity">
        <Activity events={call.events} />
      </Panel>
    </div>
  )
}
