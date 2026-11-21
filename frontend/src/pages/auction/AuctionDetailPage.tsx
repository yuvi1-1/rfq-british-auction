import { ArrowLeft, Award as AwardIcon, CalendarClock, SearchX, Ship, Timer } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'
import { Lane, StatusBadge, WindowBadge } from '../../components/AuctionBits'
import { AuctionTimeline } from '../../components/AuctionTimeline'
import { Badge } from '../../components/ui/Badge'
import { buttonClasses } from '../../components/ui/buttonClasses'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorState, Skeleton } from '../../components/ui/Feedback'
import { useRfq } from '../../hooks/queries'
import { ApiError } from '../../lib/api'
import { clockParts } from '../../lib/clock'
import { cn } from '../../lib/cn'
import { formatDate, formatDuration, formatMoney, formatTime, plural } from '../../lib/format'
import { deriveStatus, inTriggerWindow, TRIGGER_META } from '../../lib/status'
import { useNow } from '../../lib/time'
import type { AuctionStatus, RankingEntry, RfqDetail } from '../../lib/types'
import { ActivityLog } from './ActivityLog'
import { AwardCard, AwardDialog } from './Award'
import { ConfigCard } from './ConfigCard'
import { QuoteForm } from './QuoteForm'
import { RankingCard } from './RankingCard'
import { SupplierBidsCard, SupplierPositionCard } from './SupplierPanels'

export function AuctionDetailPage() {
  const { rfqId = '' } = useParams()
  const { data: rfq, isLoading, error, refetch } = useRfq(rfqId)
  const now = useNow()
  const [awardTarget, setAwardTarget] = useState<RankingEntry | null>(null)
  useOutbidAlert(rfq)

  if (error && !rfq) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <Card className="mx-auto max-w-lg">
          <EmptyState
            icon={<SearchX className="size-5" />}
            title="Auction not found"
            description="It may have been removed, or the link is wrong."
            action={<Link to="/" className={buttonClasses('secondary')}>Back to auctions</Link>}
          />
        </Card>
      )
    }
    return (
      <Card>
        <ErrorState error={error} retry={() => void refetch()} />
      </Card>
    )
  }
  if (isLoading || !rfq) return <DetailSkeleton />

  const status = deriveStatus(now, rfq)
  const ended = status === 'CLOSED' || status === 'FORCE_CLOSED'
  const inWindow =
    status === 'ACTIVE' && inTriggerWindow(now, rfq.current_close_at, rfq.config.trigger_window_minutes)
  const isBuyer = rfq.viewer_role === 'BUYER'
  const canAward = isBuyer && ended && !rfq.is_awarded && rfq.ranking.length > 0

  return (
    <>
      <title>{`${rfq.reference_id} · British Auction RFQ`}</title>
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden="true" />
        All auctions
      </Link>

      <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
              {rfq.reference_id}
            </span>
            <StatusBadge status={status} />
            {inWindow && <WindowBadge />}
            {rfq.is_awarded && (
              <Badge tone="violet">
                <AwardIcon className="size-3" aria-hidden="true" />
                Awarded
              </Badge>
            )}
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{rfq.name}</h1>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-slate-600">
            {(rfq.origin || rfq.destination) && (
              <span className="flex min-w-0 items-center gap-1.5">
                <Ship className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
                <Lane origin={rfq.origin} destination={rfq.destination} />
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <CalendarClock className="size-4 text-slate-400" aria-hidden="true" />
              Pickup {formatDate(rfq.pickup_date)}
            </span>
            <span>Buyer: {rfq.buyer_company}</span>
            <span>Prices in {rfq.currency}</span>
          </div>
        </div>
        <ClockCard rfq={rfq} status={status} now={now} inWindow={inWindow} />
      </div>

      <StatTiles rfq={rfq} />

      <Card className="mt-6">
        <CardHeader
          title="Auction progress"
          icon={<Timer className="size-4" />}
          description="The close time moves out with late activity, but never past the forced close."
        />
        <CardBody className="pt-6 pb-5">
          <AuctionTimeline
            bidStartAt={rfq.bid_start_at}
            bidCloseAt={rfq.bid_close_at}
            currentCloseAt={rfq.current_close_at}
            forcedCloseAt={rfq.forced_close_at}
            windowMinutes={rfq.config.trigger_window_minutes}
            now={now}
          />
        </CardBody>
      </Card>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          {isBuyer ? (
            <RankingCard rfq={rfq} canAward={canAward} onAward={setAwardTarget} />
          ) : (
            <SupplierBidsCard rfq={rfq} />
          )}
          <ActivityLog events={rfq.events} now={now} />
        </div>
        <div className="space-y-6">
          {!isBuyer && <SupplierPositionCard rfq={rfq} />}
          {!isBuyer && <QuoteForm rfq={rfq} status={status} />}
          {(ended || rfq.award) && <AwardCard rfq={rfq} canAward={canAward} onAward={setAwardTarget} />}
          <ConfigCard rfq={rfq} />
        </div>
      </div>

      {isBuyer && (
        <AwardDialog rfq={rfq} target={awardTarget} onClose={() => setAwardTarget(null)} />
      )}
    </>
  )
}

function ClockCard({
  rfq,
  status,
  now,
  inWindow,
}: {
  rfq: RfqDetail
  status: AuctionStatus
  now: number
  inWindow: boolean
}) {
  const { label, value } = clockParts({
    status,
    now,
    bidStartAt: rfq.bid_start_at,
    currentCloseAt: rfq.current_close_at,
  })
  const { trigger_window_minutes: x, extension_minutes: y } = rfq.config
  let note: string
  if (status === 'UPCOMING') note = `Bidding opens at ${formatTime(rfq.bid_start_at)}`
  else if (inWindow) note = `In the last ${x} min: a qualifying bid adds ${y} min`
  else if (status === 'ACTIVE') note = `Forced close at ${formatTime(rfq.forced_close_at)}, whatever happens`
  else if (status === 'FORCE_CLOSED') note = 'Ran until the forced close time'
  else note = 'Bidding has ended'

  return (
    <div
      className={cn(
        'rounded-xl border px-5 py-4 shadow-sm lg:min-w-72',
        inWindow ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white',
      )}
      aria-live="off"
    >
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900 tabular-nums">{value}</p>
      <p className={cn('mt-1 text-xs', inWindow ? 'text-amber-900' : 'text-slate-500')}>{note}</p>
    </div>
  )
}

function StatTiles({ rfq }: { rfq: RfqDetail }) {
  const isBuyer = rfq.viewer_role === 'BUYER'
  const position = rfq.my_position
  const extendedMs = Date.parse(rfq.current_close_at) - Date.parse(rfq.bid_close_at)
  const tiles = [
    {
      label: 'Current lowest bid (L1)',
      value: formatMoney(rfq.lowest_bid, rfq.currency),
      sub: isBuyer
        ? rfq.ranking[0]
          ? `by ${rfq.ranking[0].supplier_name}`
          : 'No bids yet'
        : position?.rank
          ? position.is_l1
            ? 'That is you'
            : `You are L${position.rank}`
          : 'You have not bid yet',
    },
    {
      label: 'Bids',
      value: String(rfq.bid_count),
      sub: `from ${plural(rfq.supplier_count, 'supplier')}`,
    },
    {
      label: 'Time extensions',
      value: String(rfq.extension_count),
      sub: extendedMs > 0 ? `${formatDuration(extendedMs)} added in total` : 'None yet',
    },
    {
      label: 'Extension rule',
      value: `+${rfq.config.extension_minutes} min`,
      sub: `${TRIGGER_META[rfq.config.extension_trigger].short} in the last ${rfq.config.trigger_window_minutes} min`,
    },
  ]
  return (
    <dl className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
          <dt className="text-xs font-medium text-slate-500">{tile.label}</dt>
          <dd className="mt-1 truncate text-xl font-semibold text-slate-900">{tile.value}</dd>
          <dd className="mt-0.5 truncate text-xs text-slate-500">{tile.sub}</dd>
        </div>
      ))}
    </dl>
  )
}

function useOutbidAlert(rfq: RfqDetail | undefined) {
  const previous = useRef<{ id: string; rank: number | null } | null>(null)
  const rank = rfq?.my_position?.rank ?? null
  const id = rfq?.id
  useEffect(() => {
    if (!id) return
    const before = previous.current
    if (before && before.id === id && before.rank === 1 && rank !== null && rank > 1) {
      toast.warning(`You've been outbid: you're now L${rank}`, {
        description: 'Submit a lower total to win back L1.',
      })
    }
    previous.current = { id, rank }
  }, [id, rank])
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading auction">
      <Skeleton className="h-4 w-28" />
      <div className="flex justify-between gap-6">
        <div className="flex-1 space-y-3">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <Skeleton className="hidden h-24 w-72 lg:block" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
