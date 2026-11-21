import { Settings2 } from 'lucide-react'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { formatDate, formatDateTime } from '../../lib/format'
import { TRIGGER_META } from '../../lib/status'
import type { RfqDetail } from '../../lib/types'

export function ConfigCard({ rfq }: { rfq: RfqDetail }) {
  const trigger = TRIGGER_META[rfq.config.extension_trigger]
  const extended = rfq.current_close_at !== rfq.bid_close_at
  const rows: [string, string][] = [
    ['Trigger window (X)', `${rfq.config.trigger_window_minutes} min before close`],
    ['Extension duration (Y)', `${rfq.config.extension_minutes} min per trigger`],
    ['Bid start', formatDateTime(rfq.bid_start_at)],
    [extended ? 'Original bid close' : 'Bid close', formatDateTime(rfq.bid_close_at)],
    ...(extended ? ([['Current bid close', formatDateTime(rfq.current_close_at)]] as [string, string][]) : []),
    ['Forced bid close', formatDateTime(rfq.forced_close_at)],
    ['Pickup / service date', formatDate(rfq.pickup_date)],
  ]

  return (
    <Card>
      <CardHeader title="Auction configuration" icon={<Settings2 className="size-4" />} />
      <CardBody className="space-y-4">
        <div className="rounded-lg bg-slate-50 px-3.5 py-3 ring-1 ring-slate-200 ring-inset">
          <p className="text-xs font-medium text-slate-500">Extension trigger</p>
          <p className="mt-0.5 text-sm font-medium text-slate-900">{trigger.label}</p>
          <p className="mt-1 text-xs text-slate-600">{trigger.description}</p>
        </div>
        <dl className="divide-y divide-slate-100 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 py-2">
              <dt className="text-slate-500">{label}</dt>
              <dd className="text-right font-medium text-slate-900 tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </CardBody>
    </Card>
  )
}
