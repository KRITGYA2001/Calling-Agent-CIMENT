import type { ReactNode } from 'react'

const TONES: Record<string, string> = {
  neutral: 'bg-white/5 text-zinc-300 ring-white/10',
  green: 'bg-emerald-500/10 text-emerald-300 ring-emerald-400/20',
  amber: 'bg-amber-500/10 text-amber-300 ring-amber-400/20',
  red: 'bg-red-500/10 text-red-300 ring-red-400/20',
  blue: 'bg-accent/10 text-accent ring-accent/25',
  violet: 'bg-zinc-400/10 text-zinc-200 ring-zinc-300/20',
}

export function Badge({ tone = 'neutral', children, pulse }: { tone?: keyof typeof TONES; children: ReactNode; pulse?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {pulse && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {children}
    </span>
  )
}

export function statusTone(status: string): keyof typeof TONES {
  switch (status) {
    case 'in_progress':
    case 'calling':
    case 'dialling':
      return 'blue'
    case 'completed':
      return 'green'
    case 'escalated':
      return 'amber'
    case 'blocked':
    case 'dnc_blocked':
    case 'declined':
      return 'red'
    case 'callback':
    case 'callback_requested':
      return 'violet'
    default:
      return 'neutral'
  }
}

export function Panel({ title, right, children, className = '' }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-line bg-surface ${className}`}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="text-sm font-semibold tracking-tight text-zinc-100">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}
