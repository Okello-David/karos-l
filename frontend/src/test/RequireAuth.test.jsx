import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import RequireAuth from '../components/RequireAuth'

vi.mock('../services/auth', () => ({
  authService: {
    isAuthenticated: vi.fn(),
  },
}))

import { authService } from '../services/auth'

function renderWithGuard() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/" element={<RequireAuth><div>Protected Page</div></RequireAuth>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RequireAuth', () => {
  it('renders protected content when authenticated', () => {
    authService.isAuthenticated.mockReturnValue(true)
    renderWithGuard()
    expect(screen.getByText('Protected Page')).toBeInTheDocument()
  })

  it('redirects to login when not authenticated', () => {
    authService.isAuthenticated.mockReturnValue(false)
    renderWithGuard()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })
})
