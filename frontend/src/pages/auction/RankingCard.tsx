import { Gavel, ListOrdered } from 'lucide-react'
import { useState } from 'react'
import { RankBadge } from '../../components/AuctionBits'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/Feedback'
import { Segmented } from '../../components/ui/Segmented'
import { cn } from '../../lib/cn'
import { formatDate, formatDateTime, formatMoney, formatTimeWithSeconds } from '../../lib/format'
import type { Bid, RankingEntry, RfqDetail } from '../../lib/types'

const th = 'px-3 py-2.5 font-medium whitespace-nowrap'
const td = 'px-3 py-3 whitespace-nowrap'

export function RankingCard({
  rfq,
  canAward,
  onAward,
}: {
  rfq: RfqDetail
  canAward: boolean
  onAward: (entry: RankingEntry) => void
}) {
  const [view, setView] = useState<'ranking' | 'bids'>('ranking')
  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Supplier bids"
        icon={<ListOrdered className="size-4" />}
        description="Ranked by total price (freight + origin + destination). Each supplier's lowest bid counts; on a tie, the earlier bid ranks higher."
        actions={
          <Segmented
            label="Bid view"
            value={view}
            onChange={setView}
            options={[
              { value: 'ranking', label: 'Ranking', count: rfq.ranking.length },
              { value: 'bids', label: 'All bids', count: rfq.bids.length },
            ]}
          />
        }
      />
      {rfq.bids.length === 0 ? (
        <EmptyState
          icon={<Gavel className="size-5" />}
          title="No bids yet"
          description="Bids appear here the moment suppliers submit them."
        />
      ) : view === 'ranking' ? (
        <RankingTable rfq={rfq} canAward={canAward} onAward={onAward} />
      ) : (
        <AllBidsTable bids={rfq.bids} currency={rfq.currency} />
      )}
    </Card>
  )
}

function RankingTable({
  rfq,
  canAward,
  onAward,
}: {
  rfq: RfqDetail
  canAward: boolean
  onAward: (entry: RankingEntry) => void
}) {
  const money = (value: string) => formatMoney(value, rfq.currency)
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[920px] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
          <tr>
            <th scope="col" className={cn(th, 'pl-5')}>Rank</th>
            <th scope="col" className={th}>Supplier</th>
            <th scope="col" className={th}>Carrier</th>
            <th scope="col" className={cn(th, 'text-right')}>Freight</th>
            <th scope="col" className={cn(th, 'text-right')}>Origin</th>
            <th scope="col" className={cn(th, 'text-right')}>Destination</th>
            <th scope="col" className={cn(th, 'text-right')}>Total</th>
            <th scope="col" className={cn(th, 'text-right')}>Transit</th>
            <th scope="col" className={th}>Valid until</th>
            <th scope="col" className={cn(th, 'pr-5')}>{canAward ? 'Award' : 'Last bid'}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 tabular-nums">
          {rfq.ranking.map((entry) => {
            const bid = entry.bid
            const awarded = rfq.award?.bid_id === bid.id
            return (
              <tr key={entry.supplier_id} className={cn(entry.rank === 1 && 'bg-amber-50/40', awarded && 'bg-violet-50/60')}>
                <td className={cn(td, 'pl-5')}>
                  <RankBadge rank={entry.rank} />
                </td>
                <td className={td}>
                  <div className="font-medium text-slate-900">{entry.supplier_name}</div>
                  <div className="text-xs text-slate-500">
                    {entry.bid_count} {entry.bid_count === 1 ? 'bid' : 'bids'}
                  </div>
                </td>
                <td className={cn(td, 'text-slate-700')}>{bid.carrier_name}</td>
                <td className={cn(td, 'text-right text-slate-600')}>{money(bid.freight_charges)}</td>
                <td className={cn(td, 'text-right text-slate-600')}>{money(bid.origin_charges)}</td>
                <td className={cn(td, 'text-right text-slate-600')}>{money(bid.destination_charges)}</td>
                <td className={cn(td, 'text-right font-semibold text-slate-900')}>{money(bid.total_amount)}</td>
                <td className={cn(td, 'text-right text-slate-600')}>{bid.transit_time_days} d</td>
                <td className={cn(td, 'text-slate-600')}>{formatDate(bid.quote_validity_date)}</td>
                <td className={cn(td, 'pr-5')}>
                  {canAward ? (
                    <Button size="sm" variant={entry.rank === 1 ? 'primary' : 'secondary'} onClick={() => onAward(entry)}>
                      Award
                    </Button>
                  ) : awarded ? (
                    <Badge tone="violet">Awarded</Badge>
                  ) : (
                    <span className="text-slate-500" title={formatDateTime(bid.created_at)}>
                      {formatTimeWithSeconds(bid.created_at)}
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function AllBidsTable({
  bids,
  currency,
  showSupplier = true,
}: {
  bids: Bid[]
  currency: string
  showSupplier?: boolean
}) {
  const money = (value: string) => formatMoney(value, currency)
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
          <tr>
            <th scope="col" className={cn(th, 'pl-5 text-right')}>Total</th>
            {showSupplier && <th scope="col" className={th}>Supplier</th>}
            <th scope="col" className={th}>Carrier</th>
            <th scope="col" className={cn(th, 'text-right')}>Freight</th>
            <th scope="col" className={cn(th, 'text-right')}>Origin</th>
            <th scope="col" className={cn(th, 'text-right')}>Destination</th>
            <th scope="col" className={cn(th, 'text-right')}>Transit</th>
            <th scope="col" className={th}>Valid until</th>
            <th scope="col" className={th}>Submitted</th>
            <th scope="col" className={cn(th, 'pr-5')}>
              <span className="sr-only">Counts for ranking</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 tabular-nums">
          {bids.map((bid) => (
            <tr key={bid.id} className={cn(!bid.is_best && 'text-slate-400')}>
              <td className={cn(td, 'pl-5 text-right font-semibold', bid.is_best ? 'text-slate-900' : 'text-slate-400')}>
                {money(bid.total_amount)}
              </td>
              {showSupplier && (
                <td className={cn(td, bid.is_best ? 'text-slate-900' : 'text-slate-500')}>{bid.supplier_name}</td>
              )}
              <td className={td}>{bid.carrier_name}</td>
              <td className={cn(td, 'text-right')}>{money(bid.freight_charges)}</td>
              <td className={cn(td, 'text-right')}>{money(bid.origin_charges)}</td>
              <td className={cn(td, 'text-right')}>{money(bid.destination_charges)}</td>
              <td className={cn(td, 'text-right')}>{bid.transit_time_days} d</td>
              <td className={td}>{formatDate(bid.quote_validity_date)}</td>
              <td className={td} title={formatDateTime(bid.created_at)}>
                {formatTimeWithSeconds(bid.created_at)}
              </td>
              <td className={cn(td, 'pr-5')}>
                {bid.is_best ? <Badge tone="blue">Counts</Badge> : <span className="text-xs">Superseded</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
