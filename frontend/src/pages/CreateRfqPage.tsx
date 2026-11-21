import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft, CalendarClock, CircleCheck, CircleX, Lock, Package, Timer } from 'lucide-react'
import { useState } from 'react'
import { type Control, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'
import { AuctionTimeline } from '../components/AuctionTimeline'
import { Button } from '../components/ui/Button'
import { buttonClasses } from '../components/ui/buttonClasses'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/Feedback'
import { Field, Input, Select } from '../components/ui/Field'
import { useCreateRfq } from '../hooks/queries'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { ApiError } from '../lib/api'
import { cn } from '../lib/cn'
import { formatDateTime, formatDuration } from '../lib/format'
import { TRIGGER_META, TRIGGERS } from '../lib/status'
import { serverNow, toLocalDateValue, toLocalInputValue } from '../lib/time'
import type { RfqCreatePayload } from '../lib/types'

const wholeMinutes = (label: string) =>
  z
    .string()
    .trim()
    .refine(
      (value) => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 1440,
      `${label} must be a whole number of minutes (1 to 1440)`,
    )

// same checks as the API
const schema = z
  .object({
    name: z.string().trim().min(3, 'Use at least 3 characters').max(200),
    reference_id: z
      .string()
      .trim()
      .max(40)
      .refine(
        (value) => value === '' || /^[A-Za-z0-9][A-Za-z0-9._/-]{2,39}$/.test(value),
        'Use 3 to 40 letters, numbers, or . _ / -',
      ),
    origin: z.string().trim().max(120),
    destination: z.string().trim().max(120),
    currency: z.enum(['USD', 'EUR', 'INR']),
    pickup_date: z.string().min(1, 'Choose the pickup or service date'),
    bid_start_at: z.string().min(1, 'Choose when bidding starts'),
    bid_close_at: z.string().min(1, 'Choose when bidding closes'),
    forced_close_at: z.string().min(1, 'Choose the forced close time'),
    trigger_window_minutes: wholeMinutes('The trigger window'),
    extension_minutes: wholeMinutes('The extension'),
    extension_trigger: z.enum(['BID_RECEIVED', 'ANY_RANK_CHANGE', 'L1_RANK_CHANGE']),
  })
  .superRefine((values, ctx) => {
    const start = Date.parse(values.bid_start_at)
    const close = Date.parse(values.bid_close_at)
    const forced = Date.parse(values.forced_close_at)
    if (close <= start) {
      ctx.addIssue({ code: 'custom', path: ['bid_close_at'], message: 'Must be later than the bid start time' })
    } else if (close <= serverNow()) {
      ctx.addIssue({ code: 'custom', path: ['bid_close_at'], message: 'Must be in the future' })
    }
    if (forced <= close) {
      ctx.addIssue({
        code: 'custom',
        path: ['forced_close_at'],
        message: 'Must be later than the bid close time',
      })
    }
    if (values.pickup_date < toLocalDateValue(new Date(serverNow()))) {
      ctx.addIssue({ code: 'custom', path: ['pickup_date'], message: 'Cannot be in the past' })
    }
  })

type FormValues = z.infer<typeof schema>

function defaultValues(): FormValues {
  const fiveMinutes = 5 * 60_000
  const start = new Date(Math.ceil(serverNow() / fiveMinutes) * fiveMinutes)
  const close = new Date(start.getTime() + 60 * 60_000)
  const forced = new Date(close.getTime() + 30 * 60_000)
  const pickup = new Date(close.getTime() + 7 * 86_400_000)
  return {
    name: '',
    reference_id: '',
    origin: '',
    destination: '',
    currency: 'USD',
    pickup_date: toLocalDateValue(pickup),
    bid_start_at: toLocalInputValue(start),
    bid_close_at: toLocalInputValue(close),
    forced_close_at: toLocalInputValue(forced),
    trigger_window_minutes: '10',
    extension_minutes: '5',
    extension_trigger: 'BID_RECEIVED',
  }
}

const TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone

export function CreateRfqPage() {
  const { user } = useCurrentUser()
  const navigate = useNavigate()
  const create = useCreateRfq()
  const [initial] = useState(defaultValues)
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: initial, mode: 'onTouched' })

  if (user && user.role !== 'BUYER') {
    return (
      <Card className="mx-auto max-w-lg">
        <EmptyState
          icon={<Lock className="size-5" />}
          title="Only buyers create RFQs"
          description="Switch to the buyer account in the top-right corner to create one."
          action={<Link to="/" className={buttonClasses('secondary')}>Back to auctions</Link>}
        />
      </Card>
    )
  }

  const onSubmit = handleSubmit((values) => {
    const payload: RfqCreatePayload = {
      name: values.name,
      reference_id: values.reference_id || null,
      origin: values.origin || null,
      destination: values.destination || null,
      currency: values.currency,
      pickup_date: values.pickup_date,
      bid_start_at: new Date(values.bid_start_at).toISOString(),
      bid_close_at: new Date(values.bid_close_at).toISOString(),
      forced_close_at: new Date(values.forced_close_at).toISOString(),
      trigger_window_minutes: Number(values.trigger_window_minutes),
      extension_minutes: Number(values.extension_minutes),
      extension_trigger: values.extension_trigger,
    }
    create.mutate(payload, {
      onSuccess: (rfq) => {
        toast.success(`${rfq.reference_id} created`, { description: rfq.name })
        navigate(`/rfqs/${rfq.id}`)
      },
      onError: (error) => {
        if (error instanceof ApiError) {
          for (const [field, message] of Object.entries(error.fieldErrors)) {
            if (field in values) setError(field as keyof FormValues, { message })
          }
        }
        toast.error('Could not create the RFQ', { description: error.message })
      },
    })
  })

  const fieldProps = (name: keyof FormValues) => ({
    id: name,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
    ...register(name),
  })

  return (
    <>
      <title>New RFQ · British Auction RFQ</title>
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden="true" />
        All auctions
      </Link>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">New RFQ</h1>
      <p className="mt-1 text-sm text-slate-600">
        Ask suppliers for freight quotes and let them compete in a British (reverse) auction.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="RFQ details" icon={<Package className="size-4" />} />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Field label="RFQ name" htmlFor="name" required error={errors.name?.message} className="sm:col-span-2">
                <Input placeholder="e.g. FCL 40' HC: Shanghai to Nhava Sheva" {...fieldProps('name')} />
              </Field>
              <Field label="Reference ID" htmlFor="reference_id" error={errors.reference_id?.message}
                hint="Leave empty to get the next number, like RFQ-2026-0012.">
                <Input placeholder="Auto-generated" {...fieldProps('reference_id')} />
              </Field>
              <Field label="Currency" htmlFor="currency" error={errors.currency?.message}>
                <Select {...fieldProps('currency')}>
                  <option value="USD">USD: US dollar</option>
                  <option value="EUR">EUR: Euro</option>
                  <option value="INR">INR: Indian rupee</option>
                </Select>
              </Field>
              <Field label="Origin" htmlFor="origin" error={errors.origin?.message}>
                <Input placeholder="e.g. Shanghai, CN (CNSHA)" {...fieldProps('origin')} />
              </Field>
              <Field label="Destination" htmlFor="destination" error={errors.destination?.message}>
                <Input placeholder="e.g. Nhava Sheva, IN (INNSA)" {...fieldProps('destination')} />
              </Field>
              <Field label="Pickup / service date" htmlFor="pickup_date" required error={errors.pickup_date?.message}>
                <Input type="date" {...fieldProps('pickup_date')} />
              </Field>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Bidding schedule"
              icon={<CalendarClock className="size-4" />}
              description={`Times are in your timezone (${TIMEZONE}).`}
            />
            <CardBody className="grid gap-4 sm:grid-cols-3">
              <Field label="Bid start" htmlFor="bid_start_at" required error={errors.bid_start_at?.message}>
                <Input type="datetime-local" {...fieldProps('bid_start_at')} />
              </Field>
              <Field label="Bid close" htmlFor="bid_close_at" required error={errors.bid_close_at?.message}>
                <Input type="datetime-local" {...fieldProps('bid_close_at')} />
              </Field>
              <Field label="Forced bid close" htmlFor="forced_close_at" required
                error={errors.forced_close_at?.message}
                hint="Later than the bid close. Extensions never go past it.">
                <Input type="datetime-local" {...fieldProps('forced_close_at')} />
              </Field>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="British auction rules"
              icon={<Timer className="size-4" />}
              description="When and by how much late activity extends the close time."
            />
            <CardBody className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Trigger window (X minutes)" htmlFor="trigger_window_minutes" required
                  error={errors.trigger_window_minutes?.message}
                  hint="How close to the bid close we watch for activity.">
                  <Input type="number" min={1} max={1440} {...fieldProps('trigger_window_minutes')} />
                </Field>
                <Field label="Extension duration (Y minutes)" htmlFor="extension_minutes" required
                  error={errors.extension_minutes?.message}
                  hint="How much time each trigger adds.">
                  <Input type="number" min={1} max={1440} {...fieldProps('extension_minutes')} />
                </Field>
              </div>
              <fieldset>
                <legend className="text-sm font-medium text-slate-700">Extension trigger</legend>
                <div className="mt-2 grid gap-3 md:grid-cols-3">
                  {TRIGGERS.map((trigger) => (
                    <label
                      key={trigger}
                      className="group relative flex cursor-pointer flex-col rounded-lg border border-slate-200 p-3.5 transition-colors hover:border-slate-300 has-[:checked]:border-blue-600 has-[:checked]:bg-blue-50/50 has-[:checked]:ring-1 has-[:checked]:ring-blue-600"
                    >
                      <input type="radio" value={trigger} className="sr-only" {...register('extension_trigger')} />
                      <span className="text-sm font-medium text-slate-900">{TRIGGER_META[trigger].label}</span>
                      <span className="mt-1 text-xs text-slate-600">{TRIGGER_META[trigger].description}</span>
                      <span className="mt-2 text-xs text-slate-500 italic">{TRIGGER_META[trigger].example}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </CardBody>
          </Card>

          <div className="flex justify-end gap-2">
            <Link to="/" className={buttonClasses('secondary')}>
              Cancel
            </Link>
            <Button type="submit" loading={create.isPending}>
              Create RFQ
            </Button>
          </div>
        </div>

        <aside className="lg:sticky lg:top-24">
          <RulesPreview control={control} />
        </aside>
      </form>
    </>
  )
}

function RulesPreview({ control }: { control: Control<FormValues> }) {
  const [start, close, forced, windowText, extensionText, trigger] = useWatch({
    control,
    name: [
      'bid_start_at',
      'bid_close_at',
      'forced_close_at',
      'trigger_window_minutes',
      'extension_minutes',
      'extension_trigger',
    ],
  })
  const startMs = Date.parse(start)
  const closeMs = Date.parse(close)
  const forcedMs = Date.parse(forced)
  const windowMinutes = Number(windowText)
  const extensionMinutes = Number(extensionText)
  const timesValid = [startMs, closeMs, forcedMs].every(Number.isFinite)
  const ordered = timesValid && startMs < closeMs && closeMs < forcedMs
  const now = serverNow()

  const checks = [
    { ok: timesValid && closeMs > startMs, label: 'Bid close is after bid start' },
    { ok: timesValid && closeMs > now, label: 'Bid close is in the future' },
    { ok: timesValid && forcedMs > closeMs, label: 'Forced close is later than bid close' },
    { ok: windowMinutes >= 1 && extensionMinutes >= 1, label: 'X and Y are at least 1 minute' },
  ]

  return (
    <Card>
      <CardHeader title="How this auction will run" />
      <CardBody className="space-y-4">
        {ordered ? (
          <>
            <AuctionTimeline
              bidStartAt={new Date(startMs).toISOString()}
              bidCloseAt={new Date(closeMs).toISOString()}
              currentCloseAt={new Date(closeMs).toISOString()}
              forcedCloseAt={new Date(forcedMs).toISOString()}
              windowMinutes={Number.isFinite(windowMinutes) ? windowMinutes : 0}
              now={now}
            />
            <p className="text-sm leading-relaxed text-slate-700">
              Bidding opens <strong>{formatDateTime(new Date(startMs).toISOString())}</strong> and is
              set to close at <strong>{formatDateTime(new Date(closeMs).toISOString())}</strong>. If{' '}
              {TRIGGER_META[trigger].condition} in the last {windowMinutes || 'X'} min before the
              close, the close moves <strong>{extensionMinutes || 'Y'} min</strong> later, as often as
              needed, but never past <strong>{formatDateTime(new Date(forcedMs).toISOString())}</strong>{' '}
              (at most {formatDuration(forcedMs - closeMs)} of extensions).
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-500">Set valid start, close and forced close times to see the timeline.</p>
        )}
        <ul className="space-y-1.5">
          {checks.map((check) => (
            <li key={check.label} className={cn('flex items-center gap-2 text-sm', check.ok ? 'text-slate-700' : 'text-red-600')}>
              {check.ok ? (
                <CircleCheck className="size-4 text-emerald-600" aria-hidden="true" />
              ) : (
                <CircleX className="size-4" aria-hidden="true" />
              )}
              {check.label}
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  )
}
