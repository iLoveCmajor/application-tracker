import { describe, expect, it } from 'vitest'
import { formatDate, formatRate, formatTimestamp } from './format'

describe('ac7_9 formatRate', () => {
  it.each([
    [0.333, '33.3%'],
    [1, '100%'],
    [0, '0%'],
    [null, 'n/a'],
    [0.5, '50%'],
    [0.667, '66.7%'],
  ])('%s → %s', (rate, text) => {
    expect(formatRate(rate)).toBe(text)
  })
})

describe('formatTimestamp', () => {
  it('shows the UTC date and time', () => {
    expect(formatTimestamp('2026-11-04T14:05:09.123456Z')).toBe('4 Nov 2026, 14:05 UTC')
    expect(formatTimestamp('2026-11-04T23:30:00-02:00')).toBe('5 Nov 2026, 01:30 UTC')
  })

  it('returns anything unparseable as is', () => {
    expect(formatTimestamp('soon')).toBe('soon')
  })
})

describe('formatDate', () => {
  it('formats a date and shows a dash for none', () => {
    expect(formatDate('2026-11-04')).toBe('4 Nov 2026')
    expect(formatDate(null)).toBe('—')
  })
})
