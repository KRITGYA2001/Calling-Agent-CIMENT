import type { CallState, JourneyDefinition, JourneyField, JourneySection } from './types'

export interface NextAsk {
  field: JourneyField
  section: JourneySection
  isRetry: boolean
  onFile: string | null
}

/** Mirrors the backend's server-driven "what to ask next": consent first, then from the resume section. */
export function nextAsk(call: CallState, journey: JourneyDefinition): NextAsk | null {
  const all = journey.sections
  const consent = all[0]?.fields.find((f) => f.id === 'consent_recording')
  if (call.consent !== true && consent) {
    return { field: consent, section: all[0], isRetry: (call.failures[consent.id] ?? 0) > 0, onFile: null }
  }
  const start = Math.max(0, all.findIndex((s) => s.id === call.resume_section))
  const ordered = [...all.slice(start), ...all.slice(0, start)]
  let optional: NextAsk | null = null
  for (const s of ordered) {
    for (const f of s.fields) {
      if (f.id === 'confirm_details' || call.sources[f.id] === 'voice') continue
      const ask = { field: f, section: s, isRetry: (call.failures[f.id] ?? 0) > 0, onFile: call.fields[f.id] ?? null }
      if (f.required) return ask
      optional = optional ?? ask
    }
  }
  if (optional) return optional
  const confirm = all.flatMap((s) => s.fields).find((f) => f.id === 'confirm_details')
  const sec = all[all.length - 1]
  return confirm ? { field: confirm, section: sec, isRetry: (call.failures[confirm.id] ?? 0) > 0, onFile: null } : null
}

export const fmtDuration = (s: number | null | undefined) => {
  if (s == null) return '-'
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

export const isLive = (c: CallState) => c.status === 'dialling' || c.status === 'in_progress'

export const STATUS_LABEL: Record<string, string> = {
  dialling: 'Dialling',
  in_progress: 'Live',
  escalated: 'Escalated',
  completed: 'Completed',
  declined: 'Declined',
  callback: 'Callback',
  ended: 'Ended',
  blocked: 'Blocked (DNC)',
  new: 'Ready',
  calling: 'On call',
  no_answer: 'No answer',
  dropped: 'Dropped',
  dnc_blocked: 'Blocked (DNC)',
  callback_requested: 'Callback',
}
