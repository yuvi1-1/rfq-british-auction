const moneyFormatters = new Map<string, Intl.NumberFormat>()

export function formatMoney(value: string | number | null | undefined, currency = 'USD'): string {
  if (value === null || value === undefined || value === '') return '—'
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return '—'
  let formatter = moneyFormatters.get(currency)
  if (!formatter) {
    formatter = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    moneyFormatters.set(currency, formatter)
  }
  return formatter.format(amount)
}

const dateTimeFormat = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const timeFormat = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })
const timeWithSecondsFormat = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
})
const dateFormat = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})
const fullFormat = new Intl.DateTimeFormat('en-US', { dateStyle: 'full', timeStyle: 'long' })

/** "Nov 21, 6:05 PM" */
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso))
/** "6:05 PM" */
export const formatTime = (iso: string) => timeFormat.format(new Date(iso))
/** "6:05:30 PM" */
export const formatTimeWithSeconds = (iso: string) => timeWithSecondsFormat.format(new Date(iso))
export const formatFull = (iso: string) => fullFormat.format(new Date(iso))

/** "2026-12-15" -> "Dec 15, 2026" */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  return dateFormat.format(new Date(year, month - 1, day))
}

export function isSameDay(iso: string, now: number): boolean {
  return new Date(iso).toDateString() === new Date(now).toDateString()
}

/** "04:59", "1:02:03" or "2d 3h" */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}:${pad(minutes)}:${pad(seconds)}`
  return `${pad(minutes)}:${pad(seconds)}`
}

/** "5 min", "1 h 30 min", "2 min 30 s" */
export function formatDuration(ms: number): string {
  const totalSeconds = Math.round(Math.abs(ms) / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const parts: string[] = []
  if (hours) parts.push(`${hours} h`)
  if (minutes) parts.push(`${minutes} min`)
  if (seconds && !hours) parts.push(`${seconds} s`)
  return parts.length ? parts.join(' ') : '0 min'
}

const relative = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' })

/** "in 5 minutes", "3 hours ago", "just now" */
export function formatRelative(iso: string, now: number): string {
  const seconds = Math.round((Date.parse(iso) - now) / 1000)
  const abs = Math.abs(seconds)
  if (abs < 45) return seconds >= 0 ? 'in a few seconds' : 'just now'
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (abs < 86_400) return relative.format(Math.round(seconds / 3600), 'hour')
  return relative.format(Math.round(seconds / 86_400), 'day')
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : `${value.toFixed(digits)}%`
}

export function formatDecimal(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

export function plural(count: number, noun: string, pluralNoun = `${noun}s`): string {
  return `${count} ${count === 1 ? noun : pluralNoun}`
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}
