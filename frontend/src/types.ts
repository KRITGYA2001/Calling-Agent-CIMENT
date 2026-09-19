export type CallStatus =
  | 'dialling'
  | 'in_progress'
  | 'escalated'
  | 'completed'
  | 'declined'
  | 'callback'
  | 'ended'
  | 'blocked'

export interface Escalation {
  category: string
  reason: string
  summary_for_human: string
  ts: number
  auto?: boolean
}

export interface TranscriptLine {
  role: string
  text: string
  ts: number
}

export interface CallEvent {
  kind: string
  text: string
  ts: number
}

export interface Signal {
  type: string
  text: string
  ts: number
}

export interface CallState {
  call_id: string
  status: CallStatus
  mode: 'phone'
  started_at: number
  ended_at: number | null
  lead_id: string | null
  lead_name: string | null
  fields: Record<string, string>
  sources: Record<string, 'prefilled' | 'voice'>
  failures: Record<string, number>
  validation_errors: number
  consent: boolean | null
  transcript: TranscriptLine[]
  signals: Signal[]
  events: CallEvent[]
  escalation: Escalation | null
  outcome: string | null
  callback_time: string | null
  submission: { status: string; reference?: string; errors?: string[] } | null
  human_joined_at: number | null
  dnc_check: { allowed: boolean; checks: DncCheck[] } | null
  recording_url: string | null
  resume_section: string | null
  summary: string | null
  ended_reason: string | null
}

export interface DncCheck {
  name: string
  passed: boolean
  detail: string
}

export interface JourneyField {
  id: string
  label: string
  ask_hint: string
  type: string
  required: boolean
  options: string[] | null
  sensitive: boolean
  script: string
  reprompt: string
}

export interface JourneySection {
  id: string
  title: string
  script: string
  fields: JourneyField[]
}

export interface JourneyDefinition {
  vertical: string
  name: string
  opener_template: string
  handoff_script: string
  agent_name: string
  guardrails: string[]
  sections: JourneySection[]
}

export interface Lead {
  id: string
  first_name: string
  full_name: string
  phone: string
  dropout_when: string
  last_completed_step: string
  note: string
  prefilled: Record<string, string>
  resume_section: string
  status: string
  last_call_id: string | null
  dnc_allowed: boolean
}

export interface Metrics {
  calls_total: number
  completed: number
  escalated: number
  declined: number
  callbacks: number
  dnc_blocked: number
  completion_rate: number | null
  autonomous_completion_rate: number | null
  avg_call_seconds: number | null
  avg_completed_call_seconds: number | null
  fields_captured_by_voice: number
  validation_errors_caught: number
  human_minutes_avoided: number
  escalations_by_category: Record<string, number>
  baseline_note: string
  manual_estimate_seconds_per_journey: number | null
}
