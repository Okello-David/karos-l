import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KeyboardShortcutsHelp from '../components/KeyboardShortcutsHelp'

describe('KeyboardShortcutsHelp', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <KeyboardShortcutsHelp open={false} onClose={() => {}} />
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders shortcut list when open', () => {
    render(<KeyboardShortcutsHelp open={true} onClose={() => {}} />)
    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument()
    expect(screen.getByText('Ctrl')).toBeInTheDocument()
    expect(screen.getByText('K')).toBeInTheDocument()
    expect(screen.getByText('?')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<KeyboardShortcutsHelp open={true} onClose={onClose} />)
    await user.click(screen.getByLabelText('Close shortcuts'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when backdrop clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<KeyboardShortcutsHelp open={true} onClose={onClose} />)
    await user.click(screen.getByRole('dialog'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose on Escape', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<KeyboardShortcutsHelp open={true} onClose={onClose} />)
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('renders custom shortcuts', () => {
    const custom = [{ key: 'S', label: 'Save' }]
    render(
      <KeyboardShortcutsHelp open={true} onClose={() => {}} customShortcuts={custom} />
    )
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.getByText('S')).toBeInTheDocument()
  })
})
