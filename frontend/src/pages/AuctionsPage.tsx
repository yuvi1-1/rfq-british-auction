import { Bot, Gavel, Plus, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { InlineClock, Lane, RankBadge, StatusBadge, WindowBadge } from '../components/AuctionBits'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { buttonClasses } from '../components/ui/buttonClasses'
import { Card } from '../components/ui/Card'
import { EmptyState, ErrorState, Skeleton } from '../components/ui/Feedback'
import { Input } from '../components/ui/Field'
import { Segmented } from '../components/ui/Segmented'
import { useRfqs } from '../hooks/queries'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { cn } from '../lib/cn'
import { formatDateTime, formatMoney, formatTime, isSameDay } from '../lib/format'
import { deriveStatus, inTriggerWindow, STATUS_META, STATUS_ORDER } from '../lib/status'
import { useNow } from '../lib/time'
import type { AuctionStatus, RfqSummary } from '../lib/types'
import { DemoDialog } from './DemoDialog'

type Filter = AuctionStatus | 'ALL'

export function AuctionsPage() {
  const { user } = useCurrentUser()
  const { data, isLoading, error, refetch, isFetching } = useRfqs()
  const now = useNow()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('ALL')
  const [search, setSearch] = useState('')
  const [demoOpen, setDemoOpen] = useState(false)
  const query = useDeferredValue(search.trim().toLowerCase())
  const isBuyer = user?.role === 'BUYER'

  // status is derived on the client too so rows update when a countdown ends
  const rows = useMemo(
    () => (data ?? []).map((rfq) => ({ rfq, status: deriveStatus(now, rfq) })),
    [data, now],
  )
  const counts = useMemo(() => {
    const result: Record<Filter, number> = { ALL: rows.length, UPCOMING: 0, ACTIVE: 0, CLOSED: 0, FORCE_CLOSED: 0 }
    for (const row of rows) result[row.status] += 1
    return result
  }, [rows])
  const visible = rows.filter(
    ({ rfq, status }) =>
      (filter === 'ALL' || status === filter) &&
      (!query ||
        [rfq.name, rfq.reference_id, rfq.origin ?? '', rfq.destination ?? '']
          .join(' ')
          .toLowerCase()
          .includes(query)),
  )

  return (
    <>
      <title>Auctions · British Auction RFQ</title>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">British auctions</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Suppliers bid prices down in the open. Bids late in the auction extend the close
            time, up to a forced close that can never move.
          </p>
        </div>
        {isBuyer && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setDemoOpen(true)}>
              <Bot className="size-4" aria-hidden="true" />
              Live demo
            </Button>
            <Link to="/rfqs/new" className={buttonClasses('primary')}>
              <Plus className="size-4" aria-hidden="true" />
              New RFQ
            </Link>
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Segmented
          label="Filter by status"
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'ALL', label: 'All', count: counts.ALL },
            ...STATUS_ORDER.map((status) => ({
              value: status,
              label: STATUS_META[status].label,
              count: counts[status],
            })),
          ]}
        />
        <div className="relative md:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <Input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, RFQ ID or port"
            aria-label="Search auctions"
            className="pl-9"
          />
        </div>
      </div>

      <Card className={cn('mt-4 overflow-hidden transition-opacity', isFetching && !isLoading && 'opacity-90')}>
        {error ? (
          <ErrorState error={error} retry={() => void refetch()} />
        ) : isLoading || !user ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            icon={<Gavel className="size-5" />}
            title={rows.length === 0 ? 'No auctions yet' : 'No auctions match'}
            description={
              rows.length === 0
                ? isBuyer
                  ? 'Create an RFQ with British auction rules, or start a live demo.'
                  : 'Auctions appear here as soon as a buyer creates them.'
                : 'Try another status or search term.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3">RFQ</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3 text-right">Current lowest bid</th>
                  <th scope="col" className="px-4 py-3 text-right">Bids</th>
                  <th scope="col" className="px-4 py-3">Current bid close</th>
                  <th scope="col" className="px-5 py-3">Forced close</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visible.map(({ rfq, status }) => (
                  <AuctionRow
                    key={rfq.id}
                    rfq={rfq}
                    status={status}
                    now={now}
                    isSupplier={user.role === 'SUPPLIER'}
                    onOpen={() => navigate(`/rfqs/${rfq.id}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {isBuyer && <DemoDialog open={demoOpen} onClose={() => setDemoOpen(false)} />}
    </>
  )
}

interface AuctionRowProps {
  rfq: RfqSummary
  status: AuctionStatus
  now: number
  isSupplier: boolean
  onOpen: () => void
}

function AuctionRow({ rfq, status, now, isSupplier, onOpen }: AuctionRowProps) {
  const inWindow =
    status === 'ACTIVE' && inTriggerWindow(now, rfq.current_close_at, rfq.config.trigger_window_minutes)
  const when = (iso: string) => (isSameDay(iso, now) ? formatTime(iso) : formatDateTime(iso))
  const extended = rfq.extension_count > 0

  return (
    <tr
      onClick={onOpen}
      className={cn('cursor-pointer align-top transition-colors hover:bg-slate-50', inWindow && 'bg-amber-50/40')}
    >
      <td className="max-w-xs px-5 py-3.5">
        <Link
          to={`/rfqs/${rfq.id}`}
          onClick={(event) => event.stopPropagation()}
          className="font-medium text-slate-900 hover:text-blue-700 focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          {rfq.name}
        </Link>
        <div className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-slate-500">
          <span className="shrink-0 font-mono whitespace-nowrap text-slate-600">{rfq.reference_id}</span>
          {(rfq.origin || rfq.destination) && <span aria-hidden="true">·</span>}
          <Lane origin={rfq.origin} destination={rfq.destination} className="min-w-0" />
        </div>
      </td>
      <td className="px-4 py-3.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={status} />
          {inWindow && <WindowBadge />}
          {rfq.is_awarded && <Badge tone="violet">Awarded</Badge>}
        </div>
        <div className="mt-1">
          <InlineClock
            status={status}
            now={now}
            bidStartAt={rfq.bid_start_at}
            currentCloseAt={rfq.current_close_at}
          />
        </div>
      </td>
      <td className="px-4 py-3.5 text-right">
        <div className="font-medium text-slate-900 tabular-nums">
          {formatMoney(rfq.lowest_bid, rfq.currency)}
        </div>
        {isSupplier && rfq.my_rank !== null && (
          <div className="mt-1 flex items-center justify-end gap-1 text-xs text-slate-500">
            You <RankBadge rank={rfq.my_rank} />
          </div>
        )}
      </td>
      <td className="px-4 py-3.5 text-right tabular-nums">
        <div className="text-slate-900">{rfq.bid_count}</div>
        <div className="text-xs text-slate-500">
          {rfq.supplier_count} {rfq.supplier_count === 1 ? 'supplier' : 'suppliers'}
        </div>
      </td>
      <td className="px-4 py-3.5">
        <div className="text-slate-900 tabular-nums">{when(rfq.current_close_at)}</div>
        {extended && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Badge tone="amber">+{rfq.extension_count} ext.</Badge>
            <span className="line-through">{formatTime(rfq.bid_close_at)}</span>
          </div>
        )}
      </td>
      <td className="px-5 py-3.5 text-slate-600 tabular-nums">{when(rfq.forced_close_at)}</td>
    </tr>
  )
}
