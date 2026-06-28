import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { Skeleton, TableSkeleton, CardSkeleton } from '../components/Skeleton'

describe('Skeleton', () => {
  it('renders with base classes', () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild
    expect(el).toHaveClass('animate-pulse')
    expect(el).toHaveClass('bg-gray-100')
    expect(el).toHaveClass('rounded')
  })

  it('applies custom className', () => {
    const { container } = render(<Skeleton className="h-10 w-full" />)
    const el = container.firstChild
    expect(el).toHaveClass('h-10')
    expect(el).toHaveClass('w-full')
  })
})

describe('TableSkeleton', () => {
  it('renders specified number of rows', () => {
    const { container } = render(<TableSkeleton rows={3} cols={3} />)
    const rows = container.querySelectorAll('.flex')
    expect(rows.length).toBeGreaterThanOrEqual(4)
  })
})

describe('CardSkeleton', () => {
  it('renders specified number of cards', () => {
    const { container } = render(<CardSkeleton count={2} />)
    const cards = container.querySelectorAll('.rounded-xl')
    expect(cards).toHaveLength(2)
  })
})
