import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AuctionTimeline } from './AuctionTimeline'

const base = {
  bidStartAt: '2026-11-21T16:00:00Z',
  bidCloseAt: '2026-11-21T18:00:00Z',
  forcedCloseAt: '2026-11-21T18:30:00Z',
  windowMinutes: 10,
  now: Date.parse('2026-11-21T17:56:00Z'),
}

describe('AuctionTimeline', () => {
  it('shows the trigger window and no extension before any trigger', () => {
    render(<AuctionTimeline {...base} currentCloseAt={base.bidCloseAt} />)
    expect(screen.getByText('Trigger window')).toBeInTheDocument()
    expect(screen.getByText('last 10 min')).toBeInTheDocument()
    expect(screen.queryByText('Original close')).not.toBeInTheDocument()
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/never run past the forced close/)
  })

  it('shows the original close and the time added once extended', () => {
    render(<AuctionTimeline {...base} currentCloseAt="2026-11-21T18:10:00Z" />)
    expect(screen.getByText('Original close')).toBeInTheDocument()
    expect(screen.getByText('Current close')).toBeInTheDocument()
    expect(screen.getByText('Added by extensions')).toBeInTheDocument()
    expect(screen.getByText('10 min')).toBeInTheDocument()
  })
})
