import { Medal, Receipt, Trophy } from 'lucide-react'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/Feedback'
import { formatMoney } from '../../lib/format'
import type { RfqDetail } from '../../lib/types'
import { AllBidsTable } from './RankingCard'

export function SupplierPositionCard({ rfq }: { rfq: RfqDetail }) {
  const position = rfq.my_position
  if (!position) return null
  const money = (value: string | null) => formatMoney(value, rfq.currency)

  return (
    <Card>
      <CardHeader title="Your position" icon={<Medal className="size-4" />} />
      <CardBody>
        {position.rank === null ? (
          <p className="text-sm text-slate-600">
            You have not bid yet.{' '}
            {position.l1_total
              ? `The lowest bid so far is ${money(position.l1_total)}.`
              : 'No one has bid yet, so your first quote takes L1.'}
          </p>
        ) : (
          <>
            <div className="flex items-end gap-3">
              <span
                className={
                  position.is_l1
                    ? 'text-4xl font-semibold text-amber-600'
                    : 'text-4xl font-semibold text-slate-900'
                }
              >
                L{position.rank}
              </span>
              <span className="pb-1 text-sm text-slate-500">of {position.total_suppliers} suppliers</span>
            </div>
            {position.is_l1 ? (
              <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-emerald-700">
                <Trophy className="size-4" aria-hidden="true" />
                You are the lowest bidder.
              </p>
            ) : (
              <p className="mt-2 text-sm text-slate-600">
                Beat {money(position.l1_total)} to take L1.
              </p>
            )}
            <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm">
              <div>
                <dt className="text-xs text-slate-500">Your best total</dt>
                <dd className="mt-0.5 font-medium text-slate-900 tabular-nums">
                  {money(position.best_bid?.total_amount ?? null)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Gap to L1</dt>
                <dd className="mt-0.5 font-medium text-slate-900 tabular-nums">
                  {position.is_l1 ? '—' : money(position.gap_to_l1)}
                </dd>
              </div>
            </dl>
          </>
        )}
      </CardBody>
    </Card>
  )
}

export function SupplierBidsCard({ rfq }: { rfq: RfqDetail }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Your bids"
        icon={<Receipt className="size-4" />}
        description="Your lowest bid is the one that counts. Competitors' names and quotes stay private."
      />
      {rfq.bids.length === 0 ? (
        <EmptyState
          icon={<Receipt className="size-5" />}
          title="No bids from you yet"
          description="Submit a quote while the auction is active."
        />
      ) : (
        <AllBidsTable bids={rfq.bids} currency={rfq.currency} showSupplier={false} />
      )}
    </Card>
  )
}
