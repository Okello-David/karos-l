import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Login from '../pages/Login'

vi.mock('../services/auth', () => ({
  authService: {
    login: vi.fn(),
  },
}))

import { authService } from '../services/auth'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<div>Dashboard Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Login', () => {
  beforeEach(() => {
    authService.login.mockReset()
  })

  it('submits credentials and navigates away on success', async () => {
    authService.login.mockResolvedValue({ username: 'admin' })
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith('admin', 'secret')
    })
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
    })
  })

  it('shows an error message on failed login', async () => {
    authService.login.mockRejectedValue(new Error('Invalid credentials.'))
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Invalid credentials.')).toBeInTheDocument()
  })
})
