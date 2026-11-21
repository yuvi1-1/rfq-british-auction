import { describe, expect, it } from 'vitest'
import { formatCountdown, formatDate, formatDuration, formatMoney, formatPercent } from './format'

describe('formatters', () => {
  it('formats money in the RFQ currency', () => {
    expect(formatMoney('3275', 'USD')).toBe('$3,275.00')
    expect(formatMoney('1862.5', 'EUR')).toBe('€1,862.50')
    expect(formatMoney(null)).toBe('—')
  })

  it('formats countdowns compactly', () => {
    expect(formatCountdown(4 * 60_000 + 59_000)).toBe('04:59')
    expect(formatCountdown(3_723_000)).toBe('1:02:03')
    expect(formatCountdown(2 * 86_400_000 + 3 * 3_600_000)).toBe('2d 3h')
    expect(formatCountdown(-5_000)).toBe('00:00')
  })

  it('formats durations and percentages', () => {
    expect(formatDuration(5 * 60_000)).toBe('5 min')
    expect(formatDuration(150_000)).toBe('2 min 30 s')
    expect(formatDuration(90 * 60_000)).toBe('1 h 30 min')
    expect(formatPercent(7.456)).toBe('7.5%')
    expect(formatPercent(null)).toBe('—')
  })

  it('formats plain calendar dates without a timezone shift', () => {
    expect(formatDate('2026-12-01')).toBe('Dec 1, 2026')
  })
})
