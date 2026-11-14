import { describe, expect, it } from 'vitest'
import type { Application } from '../api'
import { EMPTY_FORM, toInput, toPatch, valuesFrom } from './form'
import { formatDate } from './format'

const app: Application = {
  id: 'a1',
  company: 'Northwind Analytics',
  role: 'ML Engineer',
  link: 'https://jobs.example.com/1',
  source: 'cold',
  status: 'applied',
  applied_date: '2026-11-02',
  follow_up_date: '2026-11-09',
  notes: null,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-02T10:00:00Z',
}

describe('toInput', () => {
  it('ac6_7 sends company, role, source and leaves empty optional fields out', () => {
    expect(toInput({ ...EMPTY_FORM, company: 'Acme', role: 'MLE', source: 'referral' })).toEqual({
      company: 'Acme',
      role: 'MLE',
      source: 'referral',
    })
  })

  it('sends link and notes when given, never a status or dates', () => {
    const input = toInput({ ...EMPTY_FORM, company: 'A', role: 'R', link: 'ftp://x', notes: 'n', applied_date: '2026-01-01' })
    expect(input).toEqual({ company: 'A', role: 'R', source: 'cold', link: 'ftp://x', notes: 'n' })
  })
})

describe('ac6_9 edit form', () => {
  it('prefills every field, dates included', () => {
    expect(valuesFrom(app)).toEqual({
      company: 'Northwind Analytics',
      role: 'ML Engineer',
      link: 'https://jobs.example.com/1',
      source: 'cold',
      notes: '',
      applied_date: '2026-11-02',
      follow_up_date: '2026-11-09',
    })
  })

  it('patches only what changed', () => {
    expect(toPatch(app, valuesFrom(app))).toEqual({})
    expect(toPatch(app, { ...valuesFrom(app), role: 'Senior ML Engineer', notes: 'Call Friday' })).toEqual({
      role: 'Senior ML Engineer',
      notes: 'Call Friday',
    })
  })

  it('sends null for a cleared optional field', () => {
    expect(toPatch(app, { ...valuesFrom(app), link: '', follow_up_date: '' })).toEqual({
      link: null,
      follow_up_date: null,
    })
  })
})

describe('formatDate', () => {
  it.each([
    [null, '—'],
    ['2026-11-04', '4 Nov 2026'],
    ['2026-01-31', '31 Jan 2026'],
    ['not a date', 'not a date'],
  ])('%s', (value, expected) => {
    expect(formatDate(value)).toBe(expected)
  })
})
