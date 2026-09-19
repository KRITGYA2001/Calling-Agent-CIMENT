import { Phone, Play } from '@phosphor-icons/react'
import type { ConsoleApi } from './useConsole'
import { STATUS_LABEL } from './script'
import { Badge, Panel, statusTone } from './ui'

export default function LeadQueue({ c }: { c: ConsoleApi }) {
  const stepLabel = (id: string) => c.journey?.sections.find((s) => s.id === id)?.title ?? 'Start'

  return (
    <Panel
      title="Dropout queue"
      right={
        <button
          onClick={c.runQueue}
          disabled={c.busy === 'queue'}
          title="Simulates the scheduler: picks the next eligible lead, checks DNC, and dials"
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-accent/85 disabled:opacity-50"
        >
          <Play size={12} weight="fill" />
          {c.busy === 'queue' ? 'Dialling' : 'Run next'}
        </button>
      }
    >
      <ul className="-m-5 divide-y divide-line">
        {c.leads.map((lead) => {
          const active = c.selected?.lead_id === lead.id
          const calling = lead.status === 'calling'
          const canDial = lead.status !== 'completed' && !calling
          return (
            <li key={lead.id} className={`px-5 py-4 transition-colors ${active ? 'bg-accent/[0.06]' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{lead.full_name}</p>
                  <p className="mt-0.5 font-mono text-xs text-zinc-500">{lead.phone}</p>
                </div>
                <Badge tone={statusTone(lead.status)} pulse={calling}>
                  {STATUS_LABEL[lead.status] ?? lead.status}
                </Badge>
              </div>
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                <dt className="text-zinc-500">Dropped</dt>
                <dd className="text-zinc-300">{lead.dropout_when}</dd>
                <dt className="text-zinc-500">Last step</dt>
                <dd className="text-zinc-300">{lead.last_completed_step === 'none' ? 'None' : stepLabel(lead.last_completed_step)}</dd>
                <dt className="text-zinc-500">Resume at</dt>
                <dd className="text-accent">{stepLabel(lead.resume_section)}</dd>
              </dl>
              <div className="mt-3 flex items-center gap-2">
                {!lead.dnc_allowed && <Badge tone="red">On DNC register</Badge>}
                <div className="ml-auto flex gap-2">
                  <button
                    onClick={() => c.dialLead(lead.id)}
                    disabled={!canDial || c.busy === `dial-${lead.id}`}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-40 ${lead.dnc_allowed ? 'bg-zinc-100 text-ink hover:bg-white' : 'bg-red-500/15 text-red-200 ring-1 ring-inset ring-red-400/30 hover:bg-red-500/25'}`}
                  >
                    <Phone size={14} weight="fill" />
                    {lead.dnc_allowed ? 'Call' : 'Try (blocked)'}
                  </button>
                </div>
              </div>
            </li>
          )
        })}
        {c.leads.length === 0 && <li className="px-5 py-6 text-sm text-zinc-500">No leads loaded.</li>}
      </ul>
    </Panel>
  )
}
