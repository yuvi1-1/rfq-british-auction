import { describe, expect, it } from 'vitest'
import { deriveStatus, inTriggerWindow } from './status'

// Mirrors backend/tests/test_engine.py so both sides agree on every boundary.
const timing = {
  bid_start_at: '2026-11-21T16:00:00Z',
  bid_close_at: '2026-11-21T18:00:00Z',
  current_close_at: '2026-11-21T18:00:00Z',
  forced_close_at: '2026-11-21T18:30:00Z',
}
const at = (time: string) => Date.parse(`2026-11-21T${time}Z`)

describe('deriveStatus', () => {
  it('follows the start, close and forced close times', () => {
    expect(deriveStatus(at('15:59:59'), timing)).toBe('UPCOMING')
    expect(deriveStatus(at('16:00:00'), timing)).toBe('ACTIVE')
    expect(deriveStatus(at('17:59:59'), timing)).toBe('ACTIVE')
    expect(deriveStatus(at('18:00:00'), timing)).toBe('CLOSED')
  })

  it('reports force closed when extensions ran into the forced close', () => {
    const capped = { ...timing, current_close_at: timing.forced_close_at }
    expect(deriveStatus(at('18:29:59'), capped)).toBe('ACTIVE')
    expect(deriveStatus(at('18:30:00'), capped)).toBe('FORCE_CLOSED')
  })
})

describe('inTriggerWindow', () => {
  it('covers the last X minutes before the close, and nothing after it', () => {
    expect(inTriggerWindow(at('17:49:59'), timing.current_close_at, 10)).toBe(false)
    expect(inTriggerWindow(at('17:50:00'), timing.current_close_at, 10)).toBe(true)
    expect(inTriggerWindow(at('17:59:59'), timing.current_close_at, 10)).toBe(true)
    expect(inTriggerWindow(at('18:00:00'), timing.current_close_at, 10)).toBe(false)
  })
})
