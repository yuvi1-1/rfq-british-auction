import { Award, CircleStop, Flag, Gavel, Lock, ScrollText, TimerReset } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Card, CardHeader } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/Feedback'
import { Segmented } from '../../components/ui/Segmented'
import { cn } from '../../lib/cn'
import { formatDateTime, formatFull, formatRelative, formatTime, formatTimeWithSeconds, isSameDay } from '../../lib/format'
import { EVENT_TITLES } from '../../lib/status'
import type { AuctionEvent, EventType } from '../../lib/types'

const ICONS: Record<EventType, { icon: ReactNode; tone: string }> = {
  RFQ_CREATED: { icon: <Flag className="size-3.5" />, tone: 'bg-slate-100 text-slate-600' },
  BID_PLACED: { icon: <Gavel className="size-3.5" />, tone: 'bg-blue-100 text-blue-700' },
  AUCTION_EXTENDED: { icon: <TimerReset className="size-3.5" />, tone: 'bg-amber-100 text-amber-800' },
  EXTENSION_CAPPED: { icon: <Lock className="size-3.5" />, tone: 'bg-orange-100 text-orange-800' },
  AUCTION_CLOSED: { icon: <CircleStop className="size-3.5" />, tone: 'bg-slate-200 text-slate-700' },
  AUCTION_FORCE_CLOSED: { icon: <CircleStop className="size-3.5" />, tone: 'bg-orange-100 text-orange-800' },
  AUCTION_AWARDED: { icon: <Award className="size-3.5" />, tone: 'bg-violet-100 text-violet-700' },
}

type Filter = 'all' | 'bids' | 'extensions'

const MATCHES: Record<Filter, (type: EventType) => boolean> = {
  all: () => true,
  bids: (type) => type === 'BID_PLACED',
  extensions: (type) => type === 'AUCTION_EXTENDED' || type === 'EXTENSION_CAPPED',
}

export function ActivityLog({ events, now }: { events: AuctionEvent[]; now: number }) {
  const [filter, setFilter] = useState<Filter>('all')
  const count = (f: Filter) => events.filter((e) => MATCHES[f](e.event_type)).length
  const visible = events.filter((event) => MATCHES[filter](event.event_type))

  return (
    <Card>
      <CardHeader
        title="Activity log"
        icon={<ScrollText className="size-4" />}
        description="Bid submissions, time extensions and the reason for each."
        actions={
          <Segmented
            label="Filter activity"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: 'All', count: events.length },
              { value: 'bids', label: 'Bids', count: count('bids') },
              { value: 'extensions', label: 'Extensions', count: count('extensions') },
            ]}
          />
        }
      />
      {visible.length === 0 ? (
        <EmptyState
          icon={<ScrollText className="size-5" />}
          title={filter === 'extensions' ? 'No extensions yet' : 'Nothing here yet'}
          description={
            filter === 'extensions'
              ? 'Extensions appear when activity in the trigger window meets the rule.'
              : undefined
          }
        />
      ) : (
        <ol className="max-h-[36rem] space-y-0 overflow-y-auto px-5 py-4">
          {visible.map((event, index) => (
            <EventItem key={event.id} event={event} now={now} last={index === visible.length - 1} />
          ))}
        </ol>
      )}
    </Card>
  )
}

function EventItem({ event, now, last }: { event: AuctionEvent; now: number; last: boolean }) {
  const meta = ICONS[event.event_type]
  const details = event.details
  const isExtension = event.event_type === 'AUCTION_EXTENDED' || event.event_type === 'EXTENSION_CAPPED'
  const oldClose = typeof details.old_close_at === 'string' ? details.old_close_at : null
  const newClose = typeof details.new_close_at === 'string' ? details.new_close_at : null
  const when = (iso: string) => (isSameDay(iso, now) ? formatTime(iso) : formatDateTime(iso))

  return (
    <li className="relative flex gap-3 pb-5">
      {!last && <span className="absolute top-7 bottom-0 left-3.5 w-px bg-slate-200" aria-hidden="true" />}
      <span className={cn('relative flex size-7 shrink-0 items-center justify-center rounded-full', meta.tone)}>
        {meta.icon}
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <p className="text-sm font-medium text-slate-900">
            {EVENT_TITLES[event.event_type]}
            {event.actor_name && <span className="font-normal text-slate-500"> · {event.actor_name}</span>}
          </p>
          <time
            dateTime={event.occurred_at}
            title={formatFull(event.occurred_at)}
            className="text-xs text-slate-500 tabular-nums"
          >
            {isSameDay(event.occurred_at, now)
              ? formatTimeWithSeconds(event.occurred_at)
              : formatDateTime(event.occurred_at)}
            <span className="hidden sm:inline"> · {formatRelative(event.occurred_at, now)}</span>
          </time>
        </div>
        <p className="mt-0.5 text-sm text-slate-600">{event.message}</p>
        {isExtension && oldClose && newClose && (
          <p
            className={cn(
              'mt-2 inline-flex flex-wrap items-center gap-1.5 rounded-md px-2 py-1 text-xs ring-1 ring-inset',
              event.event_type === 'AUCTION_EXTENDED'
                ? 'bg-amber-50 text-amber-900 ring-amber-200'
                : 'bg-orange-50 text-orange-900 ring-orange-200',
            )}
          >
            Close {when(oldClose)}
            {event.event_type === 'AUCTION_EXTENDED' ? <> → <strong>{when(newClose)}</strong></> : ' (unchanged)'}
            {details.capped === true && event.event_type === 'AUCTION_EXTENDED' && ' · capped at forced close'}
          </p>
        )}
      </div>
    </li>
  )
}
