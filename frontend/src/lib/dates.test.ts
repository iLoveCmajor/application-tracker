import { describe, expect, it } from 'vitest'
import { isOverdue, todayUtc } from './dates'

describe('ac7_9 isOverdue', () => {
  const today = '2026-11-14'

  it.each([
    ['2026-11-13', true],
    ['2026-11-14', false],
    ['2026-11-15', false],
    ['2025-12-31', true],
  ])('%s → %s', (date, overdue) => {
    expect(isOverdue(date, today)).toBe(overdue)
  })

  it('a missing date is never overdue', () => {
    expect(isOverdue(null, today)).toBe(false)
  })
})

describe('todayUtc', () => {
  it('uses the UTC day, not the local one', () => {
    expect(todayUtc(new Date('2026-11-14T23:30:00-05:00'))).toBe('2026-11-15')
    expect(todayUtc(new Date('2026-11-14T00:30:00+03:00'))).toBe('2026-11-13')
  })
})
