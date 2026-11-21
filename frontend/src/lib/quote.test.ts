import { describe, expect, it } from 'vitest'
import { beatsOwnBest, centsToAmount, quoteTotalCents, toCents } from './quote'

describe('quote arithmetic', () => {
  it('parses amounts with up to two decimals into integer cents', () => {
    expect(toCents('1234.5')).toBe(123_450)
    expect(toCents('0.07')).toBe(7)
    expect(toCents('12')).toBe(1200)
    expect(toCents('1.234')).toBeNull()
    expect(toCents('-5')).toBeNull()
    expect(toCents('')).toBeNull()
  })

  it('adds the three charges without floating-point drift', () => {
    expect(quoteTotalCents(['0.10', '0.20', '0.30'])).toBe(60)
    expect(centsToAmount(quoteTotalCents(['2400.10', '210.20', '389.70']) ?? 0)).toBe('3000.00')
    expect(quoteTotalCents(['100', '', '5'])).toBeNull()
  })

  it('requires a new bid to beat the supplier’s own best', () => {
    expect(beatsOwnBest(299_999, '3000.00')).toBe(true)
    expect(beatsOwnBest(300_000, '3000.00')).toBe(false)
    expect(beatsOwnBest(300_000, null)).toBe(true)
  })
})
