import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Spinner, { InlineSpinner } from '../components/Spinner'

describe('Spinner', () => {
  it('renders with default size', () => {
    render(<Spinner />)
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg).toHaveClass('h-6')
  })

  it('renders with label', () => {
    render(<Spinner label="Loading..." />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders with sm size', () => {
    render(<Spinner size="sm" />)
    const svg = document.querySelector('svg')
    expect(svg).toHaveClass('h-4')
  })

  it('renders with lg size', () => {
    render(<Spinner size="lg" />)
    const svg = document.querySelector('svg')
    expect(svg).toHaveClass('h-10')
  })

  it('has role status', () => {
    render(<Spinner />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})

describe('InlineSpinner', () => {
  it('renders', () => {
    render(<InlineSpinner />)
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg).toHaveClass('inline')
  })
})
