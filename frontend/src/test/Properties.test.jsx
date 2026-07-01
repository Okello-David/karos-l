import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Properties from '../pages/Properties'

vi.mock('../services/explorer', () => ({
  explorerService: {
    getHierarchy: vi.fn(),
  },
}))

import { explorerService } from '../services/explorer'

describe('Properties Page', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows created properties from the property hierarchy API', async () => {
    explorerService.getHierarchy.mockResolvedValue([
      {
        id: 1,
        name: 'Release Property',
        code: 'REL01',
        sections: [
          {
            id: 1,
            name: 'Release Block',
            units: [
              { id: 1, name: 'Release Unit', capacity: 2, current_occupant_count: 1 },
            ],
          },
        ],
      },
    ])

    render(<Properties />)

    expect(await screen.findByText('Release Property')).toBeInTheDocument()
    expect(screen.getByText('REL01')).toBeInTheDocument()
    expect(screen.getAllByText('1').length).toBeGreaterThan(0)
    expect(screen.getByText('50%')).toBeInTheDocument()
  })
})
