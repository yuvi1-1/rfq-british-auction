import { describe, expect, it } from 'vitest'
import { toApiError } from './api'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('toApiError', () => {
  it('maps FastAPI validation errors onto form fields', async () => {
    const error = await toApiError(
      json(422, {
        detail: [
          {
            loc: ['body', 'forced_close_at'],
            msg: 'Value error, Forced bid close time must be later than the bid close time',
          },
          { loc: ['body', 'trigger_window_minutes'], msg: 'Input should be greater than or equal to 1' },
        ],
      }),
    )
    expect(error.status).toBe(422)
    expect(error.fieldErrors).toEqual({
      forced_close_at: 'Forced bid close time must be later than the bid close time',
      trigger_window_minutes: 'Input should be greater than or equal to 1',
    })
    expect(error.message).toBe('Forced bid close time must be later than the bid close time')
  })

  it('keeps plain error messages from business rules', async () => {
    const error = await toApiError(json(409, { detail: 'Bidding is closed for this RFQ' }))
    expect(error.status).toBe(409)
    expect(error.message).toBe('Bidding is closed for this RFQ')
    expect(error.fieldErrors).toEqual({})
  })

  it('survives a non-JSON body', async () => {
    const error = await toApiError(new Response('Bad gateway', { status: 502 }))
    expect(error.message).toBe('Request failed (502)')
  })
})
