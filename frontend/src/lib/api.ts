import { syncServerClock } from './time'
import type {
  AuctionStatus,
  BidPayload,
  BidPlaced,
  DemoAuction,
  DemoPayload,
  Metrics,
  RfqCreatePayload,
  RfqDetail,
  RfqSummary,
  User,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

interface FastApiFieldError {
  loc?: (string | number)[]
  msg?: string
}

export async function toApiError(response: Response): Promise<ApiError> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    detail = undefined
  }
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {}
    for (const item of detail as FastApiFieldError[]) {
      const field = item.loc?.at(-1)
      if (typeof field === 'string' && item.msg && !(field in fieldErrors)) {
        fieldErrors[field] = item.msg.replace(/^Value error, /, '')
      }
    }
    const first = Object.values(fieldErrors)[0]
    return new ApiError(response.status, first ?? 'Please check the form and try again.', fieldErrors)
  }
  const message = typeof detail === 'string' ? detail : `Request failed (${response.status})`
  return new ApiError(response.status, message)
}

interface RequestOptions {
  userId?: string
  method?: 'GET' | 'POST'
  body?: unknown
}

async function request<T>(path: string, { userId, method = 'GET', body }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  // no real auth: the user picked in the header
  if (userId) headers['X-User-Id'] = userId
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  syncServerClock(response.headers.get('X-Server-Time'))
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

export const api = {
  users: () => request<User[]>('/users'),

  listRfqs: (userId: string, filters: { status?: AuctionStatus; q?: string } = {}) => {
    const params = new URLSearchParams()
    if (filters.status) params.set('status', filters.status)
    if (filters.q) params.set('q', filters.q)
    const query = params.toString()
    return request<RfqSummary[]>(`/rfqs${query ? `?${query}` : ''}`, { userId })
  },

  getRfq: (userId: string, rfqId: string) => request<RfqDetail>(`/rfqs/${rfqId}`, { userId }),

  createRfq: (userId: string, payload: RfqCreatePayload) =>
    request<RfqDetail>('/rfqs', { userId, method: 'POST', body: payload }),

  placeBid: (userId: string, rfqId: string, payload: BidPayload) =>
    request<BidPlaced>(`/rfqs/${rfqId}/bids`, { userId, method: 'POST', body: payload }),

  award: (userId: string, rfqId: string, bidId: string) =>
    request<RfqDetail>(`/rfqs/${rfqId}/award`, { userId, method: 'POST', body: { bid_id: bidId } }),

  metrics: (userId: string) => request<Metrics>('/metrics', { userId }),

  launchDemo: (userId: string, payload: DemoPayload) =>
    request<DemoAuction>('/demo/auctions', { userId, method: 'POST', body: payload }),
}
