import { formatCountdown, formatDateTime, formatTime, isSameDay } from './format'
import type { AuctionStatus } from './types'

interface ClockInput {
  status: AuctionStatus
  now: number
  bidStartAt: string
  currentCloseAt: string
}

export function clockParts({ status, now, bidStartAt, currentCloseAt }: ClockInput) {
  const at = (iso: string) => (isSameDay(iso, now) ? formatTime(iso) : formatDateTime(iso))
  switch (status) {
    case 'UPCOMING':
      return { label: 'Opens in', value: formatCountdown(Date.parse(bidStartAt) - now), live: true }
    case 'ACTIVE':
      return { label: 'Closes in', value: formatCountdown(Date.parse(currentCloseAt) - now), live: true }
    case 'CLOSED':
      return { label: 'Closed at', value: at(currentCloseAt), live: false }
    case 'FORCE_CLOSED':
      return { label: 'Force-closed at', value: at(currentCloseAt), live: false }
  }
}
