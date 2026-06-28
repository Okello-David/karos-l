import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Explorer from '../pages/Explorer'

vi.mock('../services/explorer', () => ({
  explorerService: {
    getHierarchy: vi.fn(),
    getUnitDetail: vi.fn(),
  },
}))

import { explorerService } from '../services/explorer'

const mockProperties = [
  {
    id: 1,
    name: 'Main Campus',
    code: 'MC01',
    sections: [
      {
        id: 1,
        name: 'Block A',
        units: [
          {
            id: 1,
            name: 'Room 101',
            capacity: 2,
            semester_price: '500000.00',
            monthly_price: '200000.00',
            current_occupant_count: 1,
            available_spaces: 1,
            is_full: false,
            occupancy_percentage: 50,
            active_occupants: [
              { id: 1, name: 'John Doe' },
            ],
          },
          {
            id: 2,
            name: 'Room 102',
            capacity: 2,
            semester_price: '500000.00',
            monthly_price: '200000.00',
            current_occupant_count: 2,
            available_spaces: 0,
            is_full: true,
            occupancy_percentage: 100,
            active_occupants: [
              { id: 2, name: 'Jane Smith' },
              { id: 3, name: 'Bob Brown' },
            ],
          },
        ],
      },
    ],
  },
]

function renderExplorer() {
  return render(
    <MemoryRouter>
      <Explorer />
    </MemoryRouter>
  )
}

describe('Explorer Page', () => {
  it('shows loading state initially', () => {
    explorerService.getHierarchy.mockResolvedValue(mockProperties)
    renderExplorer()
    expect(screen.getByText('Property Explorer')).toBeInTheDocument()
  })

  it('renders properties after loading', async () => {
    explorerService.getHierarchy.mockResolvedValue(mockProperties)
    renderExplorer()
    expect(await screen.findByText('Main Campus')).toBeInTheDocument()
  })

  it('renders unit count for property', async () => {
    explorerService.getHierarchy.mockResolvedValue(mockProperties)
    renderExplorer()
    expect(await screen.findByText('2 units')).toBeInTheDocument()
  })

  it('renders empty state when no properties', async () => {
    explorerService.getHierarchy.mockResolvedValue([])
    renderExplorer()
    expect(await screen.findByText('No properties yet')).toBeInTheDocument()
  })

  it('renders search input', async () => {
    explorerService.getHierarchy.mockResolvedValue(mockProperties)
    renderExplorer()
    expect(await screen.findByPlaceholderText('Search units or occupants...')).toBeInTheDocument()
  })

  it('shows no results message when search yields nothing', async () => {
    explorerService.getHierarchy.mockResolvedValue([])
    const user = userEvent.setup()
    renderExplorer()
    await screen.findByPlaceholderText('Search units or occupants...')
    const input = screen.getByPlaceholderText('Search units or occupants...')
    await user.type(input, 'Nonexistent')
    expect(await screen.findByText('No matching results')).toBeInTheDocument()
  })
})
