import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Reports from '../pages/Reports'

vi.mock('../services/reports', () => ({
  reportsService: {
    occupancy: vi.fn(),
    financial: vi.fn(),
    occupants: vi.fn(),
    export: vi.fn(),
  },
}))

import { reportsService } from '../services/reports'

const occupancyData = {
  summary: {
    total_properties: 1,
    total_units: 2,
    total_capacity: 3,
    total_occupied: 2,
    total_available: 1,
    occupancy_rate: 67,
  },
  rows: [
    {
      property: 'Kikoni Heights',
      code: 'KIK',
      units: 2,
      capacity: 3,
      occupied: 2,
      available: 1,
      occupancy_rate: 67,
    },
  ],
}

const financialData = {
  summary: {
    total_collected: '1600000.00',
    total_outstanding: '600000.00',
    payment_count: 2,
    occupants_in_arrears: 1,
    start_date: null,
    end_date: null,
  },
  by_method: [{ method: 'cash', count: 1, amount: '1200000.00' }],
  rows: [
    {
      property: 'Kikoni Heights',
      code: 'KIK',
      payments: 2,
      collected: '1600000.00',
      outstanding: '600000.00',
    },
  ],
}

describe('Reports Page', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads the occupancy report by default', async () => {
    reportsService.occupancy.mockResolvedValue(occupancyData)

    render(<Reports />)

    expect(await screen.findByText('Kikoni Heights')).toBeInTheDocument()
    expect(screen.getByText('KIK')).toBeInTheDocument()
    // Rendered in both the summary tile and the table row.
    expect(screen.getAllByText('67%').length).toBeGreaterThan(0)
  })

  it('no longer offers a disabled "Coming Soon" placeholder', async () => {
    reportsService.occupancy.mockResolvedValue(occupancyData)

    render(<Reports />)
    await screen.findByText('Kikoni Heights')

    expect(screen.queryByText('Coming Soon')).not.toBeInTheDocument()
  })

  it('switches to the financial report and formats currency', async () => {
    reportsService.occupancy.mockResolvedValue(occupancyData)
    reportsService.financial.mockResolvedValue(financialData)
    const user = userEvent.setup()

    render(<Reports />)
    await screen.findByText('Kikoni Heights')

    await user.click(screen.getByText('Financial Reports'))

    await waitFor(() => expect(reportsService.financial).toHaveBeenCalled())
    // Each figure appears twice — once in the summary tile, once in the table
    // row — so match all rather than expecting a single node.
    expect((await screen.findAllByText('UGX 1,600,000')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('UGX 600,000').length).toBeGreaterThan(0)
  })

  it('shows an empty state rather than a crash when a report has no rows', async () => {
    reportsService.occupancy.mockResolvedValue({
      summary: {
        total_properties: 0,
        total_units: 0,
        total_capacity: 0,
        total_occupied: 0,
        total_available: 0,
        occupancy_rate: 0,
      },
      rows: [],
    })

    render(<Reports />)

    expect(await screen.findByText('Nothing to report yet')).toBeInTheDocument()
  })

  it('surfaces an error with a retry action', async () => {
    reportsService.occupancy.mockRejectedValue(new Error('Report service unavailable'))

    render(<Reports />)

    expect(await screen.findByText('Report service unavailable')).toBeInTheDocument()
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('exports the selected report, passing the applied date range', async () => {
    reportsService.occupancy.mockResolvedValue(occupancyData)
    reportsService.financial.mockResolvedValue(financialData)
    reportsService.export.mockResolvedValue()
    const user = userEvent.setup()

    render(<Reports />)
    await screen.findByText('Kikoni Heights')

    await user.click(screen.getByText('Financial Reports'))
    await waitFor(() => expect(reportsService.financial).toHaveBeenCalled())

    await user.click(await screen.findByText('Export CSV'))

    expect(reportsService.export).toHaveBeenCalledWith('financial', 'csv', {
      start_date: '',
      end_date: '',
    })
  })

  it('disables export while a report has no rows to export', async () => {
    reportsService.occupancy.mockResolvedValue({
      summary: {
        total_properties: 0,
        total_units: 0,
        total_capacity: 0,
        total_occupied: 0,
        total_available: 0,
        occupancy_rate: 0,
      },
      rows: [],
    })

    render(<Reports />)
    await screen.findByText('Nothing to report yet')

    expect(screen.getByText('Export CSV').closest('button')).toBeDisabled()
  })
})
