import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import GlobalSearch from '../components/GlobalSearch'

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
  },
}))

import { api } from '../services/api'

describe('GlobalSearch', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('searches registered API endpoints without double-prefixing /api', async () => {
    api.get
      .mockResolvedValueOnce({ results: [] })
      .mockResolvedValueOnce({ results: [] })
      .mockResolvedValueOnce([{ id: 1, name: 'Main Campus', code: 'MC01' }])

    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <GlobalSearch open onClose={() => {}} />
      </MemoryRouter>
    )

    await user.type(screen.getByPlaceholderText('Search occupants, receipts, properties...'), 'main')

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/occupants/?search=main&page_size=5')
      expect(api.get).toHaveBeenCalledWith('/payments/receipts/?search=main&page_size=5')
      expect(api.get).toHaveBeenCalledWith('/properties/explorer/?search=main')
    })

    expect(await screen.findByText('Main Campus')).toBeInTheDocument()
  })
})
