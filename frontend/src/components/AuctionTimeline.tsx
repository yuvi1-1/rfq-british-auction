import { cn } from '../lib/cn'
import { formatDateTime, formatDuration, formatTime, isSameDay } from '../lib/format'

interface AuctionTimelineProps {
  bidStartAt: string
  bidCloseAt: string
  currentCloseAt: string
  forcedCloseAt: string
  windowMinutes: number
  now: number
  className?: string
}

export function AuctionTimeline({
  bidStartAt,
  bidCloseAt,
  currentCloseAt,
  forcedCloseAt,
  windowMinutes,
  now,
  className,
}: AuctionTimelineProps) {
  const start = Date.parse(bidStartAt)
  const original = Date.parse(bidCloseAt)
  const close = Date.parse(currentCloseAt)
  const forced = Date.parse(forcedCloseAt)
  const span = Math.max(forced - start, 1)
  const pct = (t: number) => Math.min(100, Math.max(0, ((t - start) / span) * 100))

  const windowStart = Math.max(close - windowMinutes * 60_000, start)
  const extendedMs = close - original
  const ended = now >= close
  const showNow = now >= start && now <= forced
  const time = (t: number) => {
    const iso = new Date(t).toISOString()
    return isSameDay(iso, now) ? formatTime(iso) : formatDateTime(iso)
  }

  const marks = [
    { key: 'start', label: 'Bid start', at: start, tick: 'bg-slate-400' },
    ...(extendedMs > 0
      ? [{ key: 'original', label: 'Original close', at: original, tick: 'bg-slate-500' }]
      : []),
    {
      key: 'close',
      label: extendedMs > 0 ? 'Current close' : 'Bid close',
      at: close,
      tick: 'bg-blue-700',
    },
    { key: 'forced', label: 'Forced close', at: forced, tick: 'bg-red-500' },
  ]

  return (
    <div className={className}>
      <div
        className="relative h-4"
        role="img"
        aria-label={`Bidding runs from ${time(start)} to ${time(close)}${
          extendedMs > 0 ? ` (extended by ${formatDuration(extendedMs)})` : ''
        }; it can never run past the forced close at ${time(forced)}.`}
      >
        <div className="absolute inset-0 overflow-hidden rounded-full bg-slate-100">
          {/* Scheduled bidding period */}
          <div
            className="absolute inset-y-0 left-0 bg-blue-200"
            style={{ width: `${pct(Math.min(original, close))}%` }}
          />
          {/* Time added by extensions */}
          {extendedMs > 0 && (
            <div
              className="bg-hatch-amber absolute inset-y-0"
              style={{ left: `${pct(original)}%`, width: `${pct(close) - pct(original)}%` }}
            />
          )}
          {/* Room left for extensions, up to the forced close */}
          <div className="bg-hatch absolute inset-y-0 right-0" style={{ left: `${pct(close)}%` }} />
          {/* Elapsed time */}
          <div
            className={cn('absolute inset-y-0 left-0', ended ? 'bg-slate-900/10' : 'bg-slate-900/15')}
            style={{ width: `${pct(Math.min(now, forced))}%` }}
          />
        </div>
        {/* Trigger window: the last X minutes before the current close */}
        {!ended && (
          <div
            className="absolute -inset-y-1 rounded-sm border-2 border-amber-500 bg-amber-300/30"
            style={{ left: `${pct(windowStart)}%`, width: `${Math.max(pct(close) - pct(windowStart), 0.6)}%` }}
            title={`Trigger window: last ${windowMinutes} min before the close`}
          />
        )}
        {/* Ticks */}
        {marks.map((mark) => (
          <div
            key={mark.key}
            className={cn('absolute -top-1.5 -bottom-1.5 w-0.5 -translate-x-1/2 rounded-full', mark.tick)}
            style={{ left: `${pct(mark.at)}%` }}
            title={`${mark.label}: ${time(mark.at)}`}
          />
        ))}
        {showNow && (
          <div
            className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-slate-900 shadow"
            style={{ left: `${pct(now)}%` }}
            title="Now"
          />
        )}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:flex sm:flex-wrap sm:gap-x-6">
        {marks.map((mark) => (
          <div key={mark.key} className="flex items-center gap-2">
            <span className={cn('h-3 w-0.5 rounded-full', mark.tick)} aria-hidden="true" />
            <dt className="text-slate-500">{mark.label}</dt>
            <dd
              className={cn(
                'font-medium text-slate-900 tabular-nums',
                mark.key === 'original' && 'text-slate-500 line-through decoration-slate-400',
              )}
            >
              {time(mark.at)}
            </dd>
          </div>
        ))}
        {!ended && (
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-sm border-2 border-amber-500 bg-amber-300/30" aria-hidden="true" />
            <dt className="text-slate-500">Trigger window</dt>
            <dd className="font-medium text-slate-900">last {windowMinutes} min</dd>
          </div>
        )}
        {extendedMs > 0 && (
          <div className="flex items-center gap-2">
            <span className="bg-hatch-amber h-3 w-3 rounded-sm" aria-hidden="true" />
            <dt className="text-slate-500">Added by extensions</dt>
            <dd className="font-medium text-slate-900">{formatDuration(extendedMs)}</dd>
          </div>
        )}
      </dl>
    </div>
  )
}
