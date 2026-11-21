import { Award as AwardIcon, PartyPopper } from 'lucide-react'
import { toast } from 'sonner'
import { RankBadge } from '../../components/AuctionBits'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { useAward } from '../../hooks/queries'
import { formatDate, formatDateTime, formatMoney } from '../../lib/format'
import type { RankingEntry, RfqDetail } from '../../lib/types'

export function AwardCard({
  rfq,
  canAward,
  onAward,
}: {
  rfq: RfqDetail
  canAward: boolean
  onAward: (entry: RankingEntry) => void
}) {
  const award = rfq.award
  const isBuyer = rfq.viewer_role === 'BUYER'
  const leader = rfq.ranking[0]

  let body
  if (award && (isBuyer || award.awarded_to_me)) {
    body = (
      <>
        {award.awarded_to_me && (
          <p className="flex items-center gap-2 text-sm font-medium text-emerald-700">
            <PartyPopper className="size-4" aria-hidden="true" />
            You won this RFQ.
          </p>
        )}
        <p className="text-sm text-slate-700">
          Awarded to <strong>{award.supplier_name}</strong> ({award.carrier_name}) at{' '}
          <strong className="tabular-nums">{formatMoney(award.total_amount, rfq.currency)}</strong>.
        </p>
        <p className="mt-1 text-xs text-slate-500">{formatDateTime(award.awarded_at)}</p>
      </>
    )
  } else if (award) {
    body = <p className="text-sm text-slate-700">This RFQ was awarded to another supplier.</p>
  } else if (rfq.bid_count === 0) {
    body = <p className="text-sm text-slate-600">Bidding ended without any bids.</p>
  } else if (canAward && leader) {
    body = (
      <>
        <p className="text-sm text-slate-600">
          Bidding has ended. Award the RFQ to any supplier's final quote from the ranking, or to
          the lowest bidder:
        </p>
        <Button className="mt-3 w-full" onClick={() => onAward(leader)}>
          <AwardIcon className="size-4" aria-hidden="true" />
          Award to L1 · {formatMoney(leader.bid.total_amount, rfq.currency)}
        </Button>
      </>
    )
  } else {
    body = <p className="text-sm text-slate-600">Bidding has ended. The buyer is reviewing the quotes.</p>
  }

  return (
    <Card>
      <CardHeader title="Award" icon={<AwardIcon className="size-4" />} />
      <CardBody>{body}</CardBody>
    </Card>
  )
}

export function AwardDialog({
  rfq,
  target,
  onClose,
}: {
  rfq: RfqDetail
  target: RankingEntry | null
  onClose: () => void
}) {
  const award = useAward(rfq.id)
  const bid = target?.bid

  const confirm = () => {
    if (!bid) return
    award.mutate(bid.id, {
      onSuccess: () => {
        toast.success(`${rfq.reference_id} awarded`, {
          description: `${bid.supplier_name} at ${formatMoney(bid.total_amount, rfq.currency)}`,
        })
        onClose()
      },
      onError: (error) => toast.error('Could not award', { description: error.message }),
    })
  }

  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      title="Award this RFQ?"
      description="The supplier is told they won; this cannot be undone."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="success" onClick={confirm} loading={award.isPending}>
            Award RFQ
          </Button>
        </>
      }
    >
      {target && bid && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div className="col-span-2 flex items-center gap-2">
            <RankBadge rank={target.rank} />
            <span className="font-medium text-slate-900">{bid.supplier_name}</span>
          </div>
          <Detail label="Carrier" value={bid.carrier_name} />
          <Detail label="Total" value={formatMoney(bid.total_amount, rfq.currency)} strong />
          <Detail label="Transit time" value={`${bid.transit_time_days} days`} />
          <Detail label="Quote valid until" value={formatDate(bid.quote_validity_date)} />
        </dl>
      )}
    </Dialog>
  )
}

function Detail({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={strong ? 'font-semibold text-slate-900 tabular-nums' : 'text-slate-900'}>{value}</dd>
    </div>
  )
}
