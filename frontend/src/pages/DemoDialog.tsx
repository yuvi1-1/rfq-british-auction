import { Bot } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { Field, Input, Select } from '../components/ui/Field'
import { useLaunchDemo } from '../hooks/queries'
import { ApiError } from '../lib/api'
import { TRIGGER_META, TRIGGERS } from '../lib/status'
import type { DemoPayload, ExtensionTrigger } from '../lib/types'

const DEFAULTS: DemoPayload = {
  extension_trigger: 'L1_RANK_CHANGE',
  duration_minutes: 3,
  trigger_window_minutes: 2,
  extension_minutes: 1,
  forced_close_after_minutes: 4,
}

export function DemoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState(DEFAULTS)
  const launch = useLaunchDemo()
  const navigate = useNavigate()

  const set = (key: Exclude<keyof DemoPayload, 'extension_trigger'>) => (value: string) =>
    setForm((current) => {
      const next = { ...current }
      next[key] = Number(value)
      return next
    })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    launch.mutate(form, {
      onSuccess: ({ rfq, bots_started }) => {
        onClose()
        navigate(`/rfqs/${rfq.id}`)
        if (bots_started) {
          toast.success(`${rfq.reference_id} is live`, {
            description: 'Bots are bidding now. Switch to Oceanic Freight Co. to bid against them.',
          })
        } else {
          toast.warning('Auction created, but the bots could not start', {
            description: 'Is the Celery worker running? You can still bid as any supplier.',
          })
        }
      },
      onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Could not start the demo'),
    })
  }

  const total = form.duration_minutes + form.forced_close_after_minutes
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Start a live demo auction"
      description={`Bots bid as four suppliers. It runs at most ${total} minutes, forced close included.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="demo-form" loading={launch.isPending}>
            <Bot className="size-4" aria-hidden="true" />
            Start demo
          </Button>
        </>
      }
    >
      <form id="demo-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Extension trigger" htmlFor="demo-trigger" className="sm:col-span-2"
          hint={TRIGGER_META[form.extension_trigger].description}>
          <Select
            id="demo-trigger"
            value={form.extension_trigger}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                extension_trigger: event.target.value as ExtensionTrigger,
              }))
            }
          >
            {TRIGGERS.map((trigger) => (
              <option key={trigger} value={trigger}>
                {TRIGGER_META[trigger].label}
              </option>
            ))}
          </Select>
        </Field>
        <NumberField id="demo-duration" label="Bid close after (min)" value={form.duration_minutes}
          min={2} max={30} onChange={set('duration_minutes')} />
        <NumberField id="demo-forced" label="Forced close after bid close (min)"
          value={form.forced_close_after_minutes} min={1} max={30}
          onChange={set('forced_close_after_minutes')} />
        <NumberField id="demo-window" label="Trigger window X (min)" value={form.trigger_window_minutes}
          min={1} max={10} onChange={set('trigger_window_minutes')} />
        <NumberField id="demo-extension" label="Extension Y (min)" value={form.extension_minutes}
          min={1} max={10} onChange={set('extension_minutes')} />
      </form>
    </Dialog>
  )
}

function NumberField(props: {
  id: string
  label: string
  value: number
  min: number
  max: number
  onChange: (value: string) => void
}) {
  return (
    <Field label={props.label} htmlFor={props.id}>
      <Input
        id={props.id}
        type="number"
        min={props.min}
        max={props.max}
        required
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </Field>
  )
}
