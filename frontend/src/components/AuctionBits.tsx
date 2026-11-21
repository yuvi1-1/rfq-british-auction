import { ArrowRight, Trophy, Zap } from 'lucide-react'
import { cn } from '../lib/cn'
import { clockParts } from '../lib/clock'
import { STATUS_META } from '../lib/status'
import type { AuctionStatus } from '../lib/types'
import { Badge } from './ui/Badge'

export function StatusBadge({ status, className }: { status: AuctionStatus; className?: string }) {
  const meta = STATUS_META[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        meta.badge,
        className,
      )}
    >
      <span
        className={cn('size-1.5 rounded-full', meta.dot, status === 'ACTIVE' && 'animate-pulse')}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  )
}

export function WindowBadge({ className }: { className?: string }) {
  return (
    <Badge tone="amber" className={className} title="New activity now can extend the close time">
      <Zap className="size-3" aria-hidden="true" />
      Extension window
    </Badge>
  )
}

export function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) {
    return (
      <Badge tone="gold" className="font-semibold">
        <Trophy className="size-3" aria-hidden="true" />
        L1
      </Badge>
    )
  }
  return <Badge className="font-semibold tabular-nums">L{rank}</Badge>
}

export function Lane({
  origin,
  destination,
  className,
}: {
  origin: string | null
  destination: string | null
  className?: string
}) {
  if (!origin && !destination) return null
  return (
    <span className={cn('inline-flex min-w-0 items-center gap-1.5', className)}>
      <span className="truncate">{origin ?? '—'}</span>
      <ArrowRight className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
      <span className="truncate">{destination ?? '—'}</span>
    </span>
  )
}

export function InlineClock(props: Parameters<typeof clockParts>[0]) {
  const { label, value, live } = clockParts(props)
  return (
    <span className="text-xs text-slate-500">
      {label}{' '}
      <span className={cn('font-medium', live ? 'text-slate-900 tabular-nums' : 'text-slate-600')}>
        {value}
      </span>
    </span>
  )
}
