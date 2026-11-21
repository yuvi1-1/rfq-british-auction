import { zodResolver } from '@hookform/resolvers/zod'
import { Send } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Field, Input, MoneyInput } from '../../components/ui/Field'
import { usePlaceBid } from '../../hooks/queries'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatMoney } from '../../lib/format'
import { beatsOwnBest, centsToAmount, quoteTotalCents, toCents } from '../../lib/quote'
import { serverNow, toLocalDateValue } from '../../lib/time'
import type { AuctionStatus, RfqDetail } from '../../lib/types'

const CARRIERS = ['Maersk', 'MSC', 'CMA CGM', 'Hapag-Lloyd', 'ONE', 'Evergreen', 'COSCO', 'HMM', 'ZIM', 'Yang Ming']

const amount = z
  .string()
  .trim()
  .min(1, 'Required')
  .refine((value) => toCents(value) !== null, 'Use a number with up to 2 decimals')

const schema = z
  .object({
    carrier_name: z.string().trim().min(2, 'Enter the carrier name').max(120),
    freight_charges: amount,
    origin_charges: amount,
    destination_charges: amount,
    transit_time_days: z
      .string()
      .trim()
      .refine((value) => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 365, 'Between 1 and 365 days'),
    quote_validity_date: z.string().min(1, 'Choose how long the quote is valid'),
  })
  .superRefine((values, ctx) => {
    const total = quoteTotalCents([values.freight_charges, values.origin_charges, values.destination_charges])
    if (total === 0) {
      ctx.addIssue({ code: 'custom', path: ['freight_charges'], message: 'The total must be more than zero' })
    }
    if (values.quote_validity_date < toLocalDateValue(new Date(serverNow()))) {
      ctx.addIssue({ code: 'custom', path: ['quote_validity_date'], message: 'Cannot be in the past' })
    }
  })

type QuoteValues = z.infer<typeof schema>

const UNAVAILABLE: Partial<Record<AuctionStatus, string>> = {
  UPCOMING: 'Bidding has not opened yet.',
  CLOSED: 'Bidding has closed.',
  FORCE_CLOSED: 'Bidding was force-closed.',
}

export function QuoteForm({ rfq, status }: { rfq: RfqDetail; status: AuctionStatus }) {
  const placeBid = usePlaceBid(rfq.id)
  const best = rfq.my_position?.best_bid ?? null
  const l1Total = rfq.my_position?.l1_total ?? null
  const open = status === 'ACTIVE'

  // only on first render so live updates don't reset the form
  const [defaults] = useState<QuoteValues>(() => ({
    carrier_name: best?.carrier_name ?? '',
    freight_charges: '',
    origin_charges: '',
    destination_charges: '',
    transit_time_days: best ? String(best.transit_time_days) : '',
    quote_validity_date: toLocalDateValue(new Date(serverNow() + 30 * 86_400_000)),
  }))
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<QuoteValues>({ resolver: zodResolver(schema), defaultValues: defaults, mode: 'onTouched' })

  const [freight, origin, destination] = useWatch({
    control,
    name: ['freight_charges', 'origin_charges', 'destination_charges'],
  })
  const totalCents = quoteTotalCents([freight, origin, destination])
  const beatsBest = totalCents === null || beatsOwnBest(totalCents, best?.total_amount)
  const l1Cents = toCents(l1Total)
  const wouldLead = totalCents !== null && (l1Cents === null || totalCents < l1Cents)

  const onSubmit = handleSubmit((values) => {
    if (totalCents === null || !beatsBest) return
    placeBid.mutate(
      {
        carrier_name: values.carrier_name,
        freight_charges: centsToAmount(toCents(values.freight_charges) ?? 0),
        origin_charges: centsToAmount(toCents(values.origin_charges) ?? 0),
        destination_charges: centsToAmount(toCents(values.destination_charges) ?? 0),
        transit_time_days: Number(values.transit_time_days),
        quote_validity_date: values.quote_validity_date,
      },
      {
        onSuccess: (result) => {
          const title = result.rank === 1 ? "Bid placed: you're L1" : `Bid placed: you're L${result.rank}`
          if (result.extended) toast.warning(title, { description: result.message })
          else toast.success(title, { description: result.message })
        },
        onError: (error) => {
          if (error instanceof ApiError) {
            for (const [field, message] of Object.entries(error.fieldErrors)) {
              if (field in values) setError(field as keyof QuoteValues, { message })
            }
          }
          toast.error('Bid not accepted', { description: error.message })
        },
      },
    )
  })

  const fieldProps = (name: keyof QuoteValues) => ({
    id: `quote-${name}`,
    disabled: !open,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `quote-${name}-error` : undefined,
    ...register(name),
  })

  return (
    <Card>
      <CardHeader
        title="Submit a quote"
        icon={<Send className="size-4" />}
        description={open ? 'Ranking uses the total of the three charges.' : UNAVAILABLE[status]}
      />
      <CardBody>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field label="Carrier" htmlFor="quote-carrier_name" required error={errors.carrier_name?.message}>
            <Input list="carrier-options" autoComplete="off" placeholder="e.g. Maersk" {...fieldProps('carrier_name')} />
            <datalist id="carrier-options">
              {CARRIERS.map((carrier) => (
                <option key={carrier} value={carrier} />
              ))}
            </datalist>
          </Field>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            <Field label="Freight" htmlFor="quote-freight_charges" required error={errors.freight_charges?.message}>
              <MoneyInput currency={rfq.currency} {...fieldProps('freight_charges')} />
            </Field>
            <Field label="Origin" htmlFor="quote-origin_charges" required error={errors.origin_charges?.message}>
              <MoneyInput currency={rfq.currency} {...fieldProps('origin_charges')} />
            </Field>
            <Field label="Destination" htmlFor="quote-destination_charges" required error={errors.destination_charges?.message}>
              <MoneyInput currency={rfq.currency} {...fieldProps('destination_charges')} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Transit time (days)" htmlFor="quote-transit_time_days" required error={errors.transit_time_days?.message}>
              <Input type="number" min={1} max={365} inputMode="numeric" {...fieldProps('transit_time_days')} />
            </Field>
            <Field label="Quote valid until" htmlFor="quote-quote_validity_date" required error={errors.quote_validity_date?.message}>
              <Input type="date" {...fieldProps('quote_validity_date')} />
            </Field>
          </div>

          <div
            className={cn(
              'rounded-lg px-4 py-3 text-sm ring-1 ring-inset',
              !beatsBest
                ? 'bg-red-50 text-red-800 ring-red-200'
                : wouldLead
                  ? 'bg-emerald-50 text-emerald-900 ring-emerald-200'
                  : 'bg-slate-50 text-slate-700 ring-slate-200',
            )}
            aria-live="polite"
          >
            <div className="flex items-baseline justify-between gap-3">
              <span>Total</span>
              <span className="text-lg font-semibold tabular-nums">
                {totalCents === null ? '—' : formatMoney(centsToAmount(totalCents), rfq.currency)}
              </span>
            </div>
            <p className="mt-1 text-xs">
              {!beatsBest
                ? `Must be lower than your current best, ${formatMoney(best?.total_amount, rfq.currency)}.`
                : totalCents === null
                  ? l1Total
                    ? `Current L1 is ${formatMoney(l1Total, rfq.currency)}.`
                    : 'No bids yet: any valid quote takes L1.'
                  : wouldLead
                    ? 'This would make you the lowest bidder (L1).'
                    : `Still above the L1 price of ${formatMoney(l1Total, rfq.currency)}.`}
            </p>
          </div>

          <Button type="submit" className="w-full" disabled={!open || !beatsBest} loading={placeBid.isPending}>
            {best ? 'Submit lower bid' : 'Submit quote'}
          </Button>
        </form>
      </CardBody>
    </Card>
  )
}
