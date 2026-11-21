export type UserRole = 'BUYER' | 'SUPPLIER'
export type AuctionStatus = 'UPCOMING' | 'ACTIVE' | 'CLOSED' | 'FORCE_CLOSED'
export type ExtensionTrigger = 'BID_RECEIVED' | 'ANY_RANK_CHANGE' | 'L1_RANK_CHANGE'
export type EventType =
  | 'RFQ_CREATED'
  | 'BID_PLACED'
  | 'AUCTION_EXTENDED'
  | 'EXTENSION_CAPPED'
  | 'AUCTION_CLOSED'
  | 'AUCTION_FORCE_CLOSED'
  | 'AUCTION_AWARDED'
export type Currency = 'USD' | 'EUR' | 'INR'
export type Money = string

export interface User {
  id: string
  name: string
  company: string
  email: string
  role: UserRole
}

export interface AuctionConfig {
  trigger_window_minutes: number
  extension_minutes: number
  extension_trigger: ExtensionTrigger
}

export interface RfqTiming {
  bid_start_at: string
  bid_close_at: string
  current_close_at: string
  forced_close_at: string
}

export interface RfqSummary extends RfqTiming {
  id: string
  reference_id: string
  name: string
  origin: string | null
  destination: string | null
  currency: string
  pickup_date: string
  status: AuctionStatus
  config: AuctionConfig
  lowest_bid: Money | null
  bid_count: number
  supplier_count: number
  extension_count: number
  is_awarded: boolean
  my_rank: number | null
}

export interface Bid {
  id: string
  supplier_id: string
  supplier_name: string
  carrier_name: string
  freight_charges: Money
  origin_charges: Money
  destination_charges: Money
  total_amount: Money
  transit_time_days: number
  quote_validity_date: string
  created_at: string
  is_best: boolean
}

export interface RankingEntry {
  rank: number
  supplier_id: string
  supplier_name: string
  bid_count: number
  bid: Bid
}

export interface SupplierPosition {
  rank: number | null
  total_suppliers: number
  best_bid: Bid | null
  l1_total: Money | null
  gap_to_l1: Money | null
  is_l1: boolean
}

export interface AuctionEvent {
  id: number
  event_type: EventType
  occurred_at: string
  actor_name: string | null
  message: string
  details: Record<string, unknown>
}

export interface Award {
  awarded_at: string
  awarded_to_me: boolean | null
  bid_id: string | null
  supplier_name: string | null
  carrier_name: string | null
  total_amount: Money | null
}

export interface RfqDetail extends RfqSummary {
  viewer_role: UserRole
  buyer_company: string
  ranking: RankingEntry[]
  bids: Bid[]
  my_position: SupplierPosition | null
  events: AuctionEvent[]
  award: Award | null
  can_bid: boolean
  can_award: boolean
}

export interface RfqCreatePayload {
  name: string
  reference_id: string | null
  origin: string | null
  destination: string | null
  currency: Currency
  pickup_date: string
  bid_start_at: string
  bid_close_at: string
  forced_close_at: string
  trigger_window_minutes: number
  extension_minutes: number
  extension_trigger: ExtensionTrigger
}

export interface BidPayload {
  carrier_name: string
  freight_charges: Money
  origin_charges: Money
  destination_charges: Money
  transit_time_days: number
  quote_validity_date: string
}

export interface BidPlaced {
  bid: Bid
  rank: number
  total_suppliers: number
  extended: boolean
  current_close_at: string
  message: string
}

export interface MetricsSummary {
  total_auctions: number
  upcoming_auctions: number
  active_auctions: number
  ended_auctions: number
  total_bids: number
  total_extensions: number
  avg_bids_per_rfq: number | null
  avg_suppliers_per_rfq: number | null
  avg_price_improvement_pct: number | null
  extended_share_pct: number | null
  late_bid_share_pct: number | null
}

export interface CohortStats {
  auctions: number
  avg_bids_per_rfq: number | null
  avg_suppliers_per_rfq: number | null
  avg_price_improvement_pct: number | null
}

export interface AuctionMetricsRow {
  id: string
  reference_id: string
  name: string
  status: AuctionStatus
  currency: string
  bid_count: number
  supplier_count: number
  extension_count: number
  opening_price: Money | null
  final_price: Money | null
  price_improvement_pct: number | null
  ended_at: string | null
}

export interface Metrics {
  summary: MetricsSummary
  extended: CohortStats
  not_extended: CohortStats
  auctions: AuctionMetricsRow[]
}

export interface DemoPayload {
  extension_trigger: ExtensionTrigger
  duration_minutes: number
  trigger_window_minutes: number
  extension_minutes: number
  forced_close_after_minutes: number
}

export interface DemoAuction {
  rfq: RfqSummary
  bots_started: boolean
}

export interface LiveMessage {
  type: 'rfq_created' | 'bid_placed' | 'auction_closed' | 'auction_awarded'
  rfq_id: string
  reference_id: string
  name: string
  current_close_at: string
  forced_close_at: string
  extension_count: number
  extension: {
    extended: boolean
    capped: boolean
    old_close_at: string
    new_close_at: string
    trigger: ExtensionTrigger
  } | null
}
