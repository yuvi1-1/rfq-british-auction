import { ChartColumn, Lock, Table2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { StatusBadge } from '../components/AuctionBits'
import { buttonClasses } from '../components/ui/buttonClasses'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState, ErrorState, Skeleton } from '../components/ui/Feedback'
import { useMetrics } from '../hooks/queries'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { cn } from '../lib/cn'
import { formatDecimal, formatMoney, formatPercent, plural } from '../lib/format'
import type { CohortStats, Metrics } from '../lib/types'

export function MetricsPage() {
  const { user } = useCurrentUser()
  const isBuyer = user?.role === 'BUYER'
  const { data, isLoading, error, refetch, isFetching } = useMetrics(isBuyer)

  if (user && !isBuyer) {
    return (
      <Card className="mx-auto max-w-lg">
        <EmptyState
          icon={<Lock className="size-5" />}
          title="Metrics are for buyers"
          description="Switch to the buyer account in the top-right corner to see them."
          action={<Link to="/" className={buttonClasses('secondary')}>Back to auctions</Link>}
        />
      </Card>
    )
  }

  return (
    <>
      <title>Metrics · British Auction RFQ</title>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Success metrics</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        Are suppliers bidding more, and do auctions that were extended end at better prices than
        ones that were not?
      </p>

      {error && !data ? (
        <Card className="mt-6">
          <ErrorState error={error} retry={() => void refetch()} />
        </Card>
      ) : isLoading || !data ? (
        <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : (
        <div className={cn('transition-opacity', isFetching && 'opacity-80')}>
          <MetricsBody metrics={data} />
        </div>
      )}
    </>
  )
}

function MetricsBody({ metrics }: { metrics: Metrics }) {
  const { summary, extended, not_extended: notExtended } = metrics
  const started = summary.total_auctions - summary.upcoming_auctions
  const ended = metrics.auctions
    .filter((row) => row.price_improvement_pct !== null && (row.status === 'CLOSED' || row.status === 'FORCE_CLOSED'))
    .sort((a, b) => (b.price_improvement_pct ?? 0) - (a.price_improvement_pct ?? 0))

  return (
    <>
      <dl className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Bids per RFQ"
          value={formatDecimal(summary.avg_bids_per_rfq)}
          sub={`${plural(summary.total_bids, 'bid')} across ${plural(started, 'started auction')}`}
        />
        <StatTile
          label="Average price improvement"
          value={formatPercent(summary.avg_price_improvement_pct)}
          sub="First bid to final L1, ended auctions"
        />
        <StatTile
          label="Auctions extended"
          value={formatPercent(summary.extended_share_pct, 0)}
          sub={`${plural(summary.total_extensions, 'extension')} in total`}
        />
        <StatTile
          label="Late bids"
          value={formatPercent(summary.late_bid_share_pct, 0)}
          sub="Placed inside a trigger window"
        />
      </dl>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <CohortChart
          title="Bids per RFQ"
          caption="Average number of bids, ended auctions"
          extended={extended}
          notExtended={notExtended}
          pick={(c) => c.avg_bids_per_rfq}
          format={(v) => formatDecimal(v)}
          unit="bids"
        />
        <CohortChart
          title="Price improvement"
          caption="Average drop from first bid to final L1"
          extended={extended}
          notExtended={notExtended}
          pick={(c) => c.avg_price_improvement_pct}
          format={(v) => formatPercent(v)}
          unit="lower"
        />
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Price improvement by auction"
          icon={<ChartColumn className="size-4" />}
          description="Ended auctions, largest improvement first."
          actions={<Legend />}
        />
        <CardBody>
          {ended.length === 0 ? (
            <p className="text-sm text-slate-500">No ended auctions with bids yet.</p>
          ) : (
            <HBars
              labelWidth="9rem"
              rows={ended.map((row) => ({
                key: row.id,
                label: (
                  <span title={row.name}>
                    <span className="font-mono text-xs text-slate-700">{row.reference_id}</span>
                  </span>
                ),
                value: row.price_improvement_pct,
                display: formatPercent(row.price_improvement_pct),
                accent: row.extension_count > 0,
                tooltip: `${formatPercent(row.price_improvement_pct)} lower · ${row.reference_id}, ${row.name} (${plural(row.extension_count, 'extension')})`,
              }))}
            />
          )}
        </CardBody>
      </Card>

      <Card className="mt-6 overflow-hidden">
        <CardHeader
          title="All auctions"
          icon={<Table2 className="size-4" />}
          description="The numbers behind the charts."
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
              <tr>
                {['RFQ', 'Status', 'Bids', 'Suppliers', 'Extensions', 'First bid', 'Final L1', 'Improvement'].map(
                  (heading, i) => (
                    <th key={heading} scope="col" className={cn('px-4 py-2.5 font-medium', i === 0 && 'pl-5', i >= 2 && 'text-right', i === 7 && 'pr-5')}>
                      {heading}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 tabular-nums">
              {metrics.auctions.map((row) => (
                <tr key={row.id}>
                  <td className="max-w-xs px-4 py-2.5 pl-5">
                    <Link to={`/rfqs/${row.id}`} className="font-mono text-xs text-blue-700 hover:underline">
                      {row.reference_id}
                    </Link>
                    <div className="truncate text-slate-700">{row.name}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-2.5 text-right">{row.bid_count}</td>
                  <td className="px-4 py-2.5 text-right">{row.supplier_count}</td>
                  <td className="px-4 py-2.5 text-right">{row.extension_count}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(row.opening_price, row.currency)}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(row.final_price, row.currency)}</td>
                  <td className="px-4 py-2.5 pr-5 text-right font-medium text-slate-900">
                    {formatPercent(row.price_improvement_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="mt-4 text-xs text-slate-500">
        Price improvement = (first bid − final L1 price) ÷ first bid. The demo data is generated
        by replaying bids through the real auction engine, so treat the numbers as illustrative.
      </p>
    </>
  )
}

function StatTile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">{value}</dd>
      <dd className="mt-1 text-xs text-slate-500">{sub}</dd>
    </div>
  )
}

function Legend() {
  return (
    <ul className="flex items-center gap-4 text-xs text-slate-600" aria-label="Legend">
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-[2px] bg-series-accent" aria-hidden="true" />
        Extended
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-[2px] bg-series-muted" aria-hidden="true" />
        Not extended
      </li>
    </ul>
  )
}

function CohortChart({
  title,
  caption,
  extended,
  notExtended,
  pick,
  format,
  unit,
}: {
  title: string
  caption: string
  extended: CohortStats
  notExtended: CohortStats
  pick: (cohort: CohortStats) => number | null
  format: (value: number | null) => string
  unit: string
}) {
  const cohorts = [
    { key: 'extended', label: 'Extended', stats: extended, accent: true },
    { key: 'not-extended', label: 'Not extended', stats: notExtended, accent: false },
  ]
  return (
    <Card>
      <CardHeader title={title} description={caption} />
      <CardBody>
        <HBars
          labelWidth="7.5rem"
          rows={cohorts.map((cohort) => {
            const value = pick(cohort.stats)
            return {
              key: cohort.key,
              label: (
                <span>
                  {cohort.label}
                  <span className="block text-xs text-slate-400">{plural(cohort.stats.auctions, 'auction')}</span>
                </span>
              ),
              value,
              display: format(value),
              accent: cohort.accent,
              tooltip: `${format(value)} ${unit} · ${cohort.label} (${plural(cohort.stats.auctions, 'auction')})`,
            }
          })}
        />
      </CardBody>
    </Card>
  )
}

interface BarRow {
  key: string
  label: ReactNode
  value: number | null
  display: string
  accent: boolean
  tooltip: string
}

function HBars({ rows, labelWidth }: { rows: BarRow[]; labelWidth: string }) {
  const max = Math.max(...rows.map((row) => row.value ?? 0), 0)
  return (
    <ul className="space-y-2">
      {rows.map((row) => {
        // leave room for the value label
        const width = row.value && max > 0 ? Math.max((row.value / max) * 80, 1) : 0
        return (
          <li
            key={row.key}
            tabIndex={0}
            aria-label={row.tooltip}
            className="group relative grid items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            style={{ gridTemplateColumns: `${labelWidth} minmax(0, 1fr)` }}
          >
            <span className="min-w-0 truncate text-sm text-slate-600">{row.label}</span>
            <div className="flex min-h-9 items-center gap-2 border-l border-slate-300">
              <div
                className={cn(
                  'h-5 rounded-r-[4px] transition-[filter] group-hover:brightness-110 group-focus-visible:brightness-110',
                  row.accent ? 'bg-series-accent' : 'bg-series-muted',
                )}
                style={{ width: `${width}%` }}
              />
              <span className="shrink-0 text-sm font-medium text-slate-900 tabular-nums">{row.display}</span>
            </div>
            <span
              role="tooltip"
              className="pointer-events-none absolute bottom-full left-1/3 z-10 mb-1 hidden rounded-md bg-slate-900 px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow-lg group-hover:block group-focus-visible:block"
            >
              {row.tooltip}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
