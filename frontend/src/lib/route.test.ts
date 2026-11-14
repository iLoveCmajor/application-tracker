import { describe, expect, it } from 'vitest'
import { href, parseRoute } from './route'

describe('ac6_4/ac7_1 parseRoute', () => {
  it.each([
    ['', { name: 'list', status: null }],
    ['#', { name: 'list', status: null }],
    ['#/', { name: 'list', status: null }],
    ['#/?status=applied', { name: 'list', status: 'applied' }],
    ['#/?status=bogus', { name: 'list', status: null }],
    ['#/new', { name: 'new' }],
    ['#/new/', { name: 'new' }],
    ['#/applications/abc-123/edit', { name: 'edit', id: 'abc-123' }],
    ['#/followups', { name: 'followups' }],
    ['#/funnel', { name: 'funnel' }],
    ['#/nowhere', { name: 'list', status: null }],
    ['#/applications/abc-123', { name: 'detail', id: 'abc-123' }],
    ['#/applications/abc-123/', { name: 'detail', id: 'abc-123' }],
    ['#/applications/abc-123/nope', { name: 'list', status: null }],
    ['#/applications//edit', { name: 'list', status: null }],
  ])('%s', (hash, route) => {
    expect(parseRoute(hash)).toEqual(route)
  })

  it('round-trips the hrefs it builds', () => {
    expect(parseRoute(href.list('ghosted'))).toEqual({ name: 'list', status: 'ghosted' })
    expect(parseRoute(href.list(null))).toEqual({ name: 'list', status: null })
    expect(parseRoute(href.edit('a/b'))).toEqual({ name: 'edit', id: 'a/b' })
    expect(parseRoute(href.new())).toEqual({ name: 'new' })
    expect(parseRoute(href.detail('a/b'))).toEqual({ name: 'detail', id: 'a/b' })
  })
})
