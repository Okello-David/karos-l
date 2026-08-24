import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/Toast'
import OccupantDetail from '../pages/OccupantDetail'

// Regression test for the duplicated-success-toast bug found during the
// 2026-08-20 production-readiness audit: RecordPaymentDialog (and, identically,
// AssignOccupancyDialog) already fires its own success toast on success —
// OccupantDetail's onRecorded/onAssigned callbacks used to ALSO fire one for
// the same single action, showing two toasts for one API call. Fixed by
// removing the redundant parent-level addToast calls (2026-08-24).

vi.mock('../services/occupants', () => ({
  occupantsService: {
    get: vi.fn(),
    archive: vi.fn(),
  },
}))
vi.mock('../services/occupancy', () => ({
  occupancyService: {
    list: vi.fn(),
    checkout: vi.fn(),
  },
}))
vi.mock('../services/payments', () => ({
  paymentsService: {
    studentBalance: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
  },
}))

import { occupantsService } from '../services/occupants'
import { occupancyService } from '../services/occupancy'
import { paymentsService } from '../services/payments'

const OCCUPANT = {
  id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  email: 'jane@example.com',
  phone: '+256700000000',
  student_id_number: 'STU001',
  national_id: 'NAT001',
  is_active: true,
  full_name: 'Jane Doe',
  created_at: '2026-01-01T00:00:00Z',
}

function renderOccupantDetail() {
  return render(
    <MemoryRouter initialEntries={['/occupants/1']}>
      <ToastProvider>
        <Routes>
          <Route path="/occupants/:id" element={<OccupantDetail />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

describe('OccupantDetail — payment/assignment success toast', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows exactly one success toast after recording a payment, not two', async () => {
    const user = userEvent.setup()
    occupantsService.get.mockResolvedValue(OCCUPANT)
    occupancyService.list.mockResolvedValue({ count: 0, results: [] })
    paymentsService.studentBalance.mockResolvedValue({ balance: '0', total_paid: '0', total_charges: '0' })
    paymentsService.list.mockResolvedValue({ results: [] })
    paymentsService.create.mockResolvedValue({ id: 99, amount: '150000.00' })

    renderOccupantDetail()

    const [openButton] = await screen.findAllByRole('button', { name: 'Record Payment' })
    await user.click(openButton)

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/Amount/), '150000')
    await user.click(within(dialog).getByRole('button', { name: 'Record Payment' }))

    // Exactly one toast, not two, for the single payment that was recorded.
    const toasts = await screen.findAllByText('Payment recorded successfully.')
    expect(toasts).toHaveLength(1)
    expect(paymentsService.create).toHaveBeenCalledTimes(1)
  })
})
