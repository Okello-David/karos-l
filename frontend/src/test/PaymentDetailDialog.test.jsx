import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PaymentDetailDialog from '../components/PaymentDetailDialog'

const payment = {
  id: 1,
  amount: '150000.00',
  student_name: 'Jane Doe',
  payment_date: '2026-06-01',
  payment_method: 'cash',
  reference: null,
  receipt_id: 1,
  receipt_number: 'RCT-0001',
  notes: null,
  created_at: '2026-06-01T10:00:00Z',
}

describe('PaymentDetailDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <PaymentDetailDialog open={false} payment={payment} onClose={() => {}} />
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders payment details without crashing when open', () => {
    render(<PaymentDetailDialog open={true} payment={payment} onClose={() => {}} />)
    expect(screen.getByText('Payment Details')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('RCT-0001')).toBeInTheDocument()
  })
})
