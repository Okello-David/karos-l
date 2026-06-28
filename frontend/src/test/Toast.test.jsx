import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider, useToast } from '../components/Toast'

function TestConsumer({ onAdd }) {
  const { addToast, dismissToast } = useToast()
  return (
    <div>
      <button onClick={() => addToast('Success!', { type: 'success' })}>Add Success</button>
      <button onClick={() => addToast('Error occurred', { type: 'error' })}>Add Error</button>
      <button onClick={() => addToast('Info', { type: 'info' })}>Add Info</button>
      <button onClick={() => {
        const id = addToast('Dismiss me', { type: 'success', duration: 999999 })
        dismissToast(id)
      }}>Add and Dismiss</button>
    </div>
  )
}

describe('Toast', () => {
  it('shows and dismisses success toast', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>
    )

    await user.click(screen.getByText('Add Success'))
    expect(screen.getByText('Success!')).toBeInTheDocument()
  })

  it('shows error toast', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>
    )

    await user.click(screen.getByText('Add Error'))
    expect(screen.getByText('Error occurred')).toBeInTheDocument()
  })

  it('dismisses toast immediately', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>
    )

    await user.click(screen.getByText('Add and Dismiss'))
    expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument()
  })

  it('throws if useToast outside provider', () => {
    expect(() => render(<TestConsumer />)).toThrow('useToast must be used within a ToastProvider')
  })
})
