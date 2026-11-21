import type { AuctionStatus, EventType, ExtensionTrigger, RfqTiming } from './types'

export function deriveStatus(now: number, timing: RfqTiming): AuctionStatus {
  const start = Date.parse(timing.bid_start_at)
  const close = Date.parse(timing.current_close_at)
  const forced = Date.parse(timing.forced_close_at)
  if (now < start) return 'UPCOMING'
  if (now < close) return 'ACTIVE'
  return close >= forced ? 'FORCE_CLOSED' : 'CLOSED'
}

export function inTriggerWindow(now: number, closeAt: string, windowMinutes: number): boolean {
  const close = Date.parse(closeAt)
  return close - windowMinutes * 60_000 <= now && now < close
}

export const STATUS_META: Record<AuctionStatus, { label: string; badge: string; dot: string }> = {
  UPCOMING: {
    label: 'Upcoming',
    badge: 'bg-sky-50 text-sky-700 ring-sky-600/20',
    dot: 'bg-sky-500',
  },
  ACTIVE: {
    label: 'Active',
    badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    dot: 'bg-emerald-500',
  },
  CLOSED: {
    label: 'Closed',
    badge: 'bg-slate-100 text-slate-700 ring-slate-500/20',
    dot: 'bg-slate-400',
  },
  FORCE_CLOSED: {
    label: 'Force closed',
    badge: 'bg-orange-50 text-orange-700 ring-orange-600/20',
    dot: 'bg-orange-500',
  },
}

export const STATUS_ORDER: AuctionStatus[] = ['ACTIVE', 'UPCOMING', 'CLOSED', 'FORCE_CLOSED']

export const TRIGGER_META: Record<
  ExtensionTrigger,
  { label: string; short: string; condition: string; description: string; example: string }
> = {
  BID_RECEIVED: {
    label: 'Bid received in the last X minutes',
    short: 'Any bid',
    condition: 'a bid is received',
    description: 'Any new bid inside the trigger window extends the auction.',
    example: 'A bid at 5:55 PM moves a 6:00 PM close to 6:05 PM.',
  },
  ANY_RANK_CHANGE: {
    label: 'Any supplier rank change in the last X minutes',
    short: 'Rank change',
    condition: "any supplier's rank changes",
    description: "Extends when a bid changes any supplier's position in the ranking.",
    example: 'Supplier B underbids Supplier A at 5:58 PM, so the close moves out.',
  },
  L1_RANK_CHANGE: {
    label: 'Lowest bidder (L1) change in the last X minutes',
    short: 'L1 change',
    condition: 'the lowest bidder (L1) changes',
    description: 'Extends only when a different supplier becomes the lowest bidder.',
    example: 'Supplier C becomes the new L1 at 5:59 PM, so the close moves out.',
  },
}

export const TRIGGERS = Object.keys(TRIGGER_META) as ExtensionTrigger[]

export const EVENT_TITLES: Record<EventType, string> = {
  RFQ_CREATED: 'RFQ created',
  BID_PLACED: 'Bid submitted',
  AUCTION_EXTENDED: 'Auction extended',
  EXTENSION_CAPPED: 'Extension blocked by forced close',
  AUCTION_CLOSED: 'Auction closed',
  AUCTION_FORCE_CLOSED: 'Auction force-closed',
  AUCTION_AWARDED: 'RFQ awarded',
}
