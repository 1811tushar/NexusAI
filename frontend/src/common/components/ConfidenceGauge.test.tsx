import { render, screen } from '@testing-library/react'
import { ConfidenceGauge } from './ConfidenceGauge'

describe('ConfidenceGauge', () => {
  it('exposes value and a low-confidence state in text', () => {
    render(<ConfidenceGauge value={0.55} threshold={0.7} />)
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '55')
    expect(screen.getByText('Low confidence')).toBeInTheDocument()
  })
  it('shows no warning at or above threshold', () => {
    render(<ConfidenceGauge value={0.8} />)
    expect(screen.queryByText('Low confidence')).toBeNull()
  })
})
