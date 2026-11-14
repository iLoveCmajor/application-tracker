import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import { createHttpApi } from './http'
import type { Api } from './types'

const api = createHttpApi('/api/v1')

function stubFetch(response: Response | Error) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('requests match openapi.yaml', () => {
  const input = { company: 'Northwind Analytics', role: 'ML Engineer', source: 'cold' as const, link: null }

  const cases: [string, (a: Api) => Promise<unknown>, string, string, unknown][] = [
    ['health', (a) => a.health(), 'GET', '/health', undefined],
    ['ready', (a) => a.ready(), 'GET', '/ready', undefined],
    ['ac6_3 list without filter', (a) => a.listApplications(), 'GET', '/api/v1/applications', undefined],
    ['ac6_3 list, empty filter', (a) => a.listApplications({}), 'GET', '/api/v1/applications', undefined],
    [
      'ac6_3 list with ?status=',
      (a) => a.listApplications({ status: 'interview' }),
      'GET',
      '/api/v1/applications?status=interview',
      undefined,
    ],
    ['ac6_3 create', (a) => a.createApplication(input), 'POST', '/api/v1/applications', input],
    ['getApplication', (a) => a.getApplication('a1'), 'GET', '/api/v1/applications/a1', undefined],
    [
      'ac6_3 patch',
      (a) => a.updateApplication('a1', { notes: null, follow_up_date: '2026-11-20' }),
      'PATCH',
      '/api/v1/applications/a1',
      { notes: null, follow_up_date: '2026-11-20' },
    ],
    [
      'ac7_9 changeStatus',
      (a) => a.changeStatus('a1', { status: 'applied', note: 'Sent' }),
      'POST',
      '/api/v1/applications/a1/status',
      { status: 'applied', note: 'Sent' },
    ],
    ['ac7_9 listEvents', (a) => a.listEvents('a1'), 'GET', '/api/v1/applications/a1/events', undefined],
    ['ac7_9 listFollowups', (a) => a.listFollowups(), 'GET', '/api/v1/followups', undefined],
    ['ac7_9 getFunnel', (a) => a.getFunnel(), 'GET', '/api/v1/stats/funnel', undefined],
  ]

  it.each(cases)('%s', async (_name, call, method, url, body) => {
    const fetchMock = stubFetch(json(200, {}))
    await call(api)
    const [calledUrl, init] = fetchMock.mock.calls[0]
    expect(calledUrl).toBe(url)
    expect(init?.method).toBe(method)
    if (body === undefined) {
      expect(init?.body).toBeUndefined()
      expect(init?.headers).toBeUndefined()
    } else {
      expect(JSON.parse(String(init?.body))).toEqual(body)
      expect(init?.headers).toEqual({ 'Content-Type': 'application/json' })
    }
  })

  it('deleteApplication returns nothing on 204', async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }))
    await expect(api.deleteApplication('a1')).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/applications/a1')
    expect(fetchMock.mock.calls[0][1]?.method).toBe('DELETE')
  })

  it('encodes ids in the path', async () => {
    const fetchMock = stubFetch(json(200, {}))
    await api.getApplication('a/b?c')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/applications/a%2Fb%3Fc')
  })

  it('puts /health and /ready under rootBase, not the API base', async () => {
    const fetchMock = stubFetch(json(200, { status: 'ok' }))
    await createHttpApi('https://x.example/api/v1', 'https://x.example').ready()
    expect(fetchMock.mock.calls[0][0]).toBe('https://x.example/ready')
  })
})

describe('responses', () => {
  it('returns the parsed body', async () => {
    stubFetch(json(200, [{ id: 'a1', company: 'Northwind Analytics' }]))
    await expect(api.listApplications()).resolves.toEqual([{ id: 'a1', company: 'Northwind Analytics' }])
  })

  it('ac6_2/ac6_3 turns the error body into a typed ApiError', async () => {
    stubFetch(
      json(422, {
        error: { code: 'validation_error', message: 'Link must start with http:// or https://', details: { field: 'link' } },
      }),
    )
    const error = await api.createApplication({ company: 'C', role: 'R', source: 'cold', link: 'ftp://x' }).catch(
      (e: unknown) => e,
    )
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 422,
      code: 'validation_error',
      message: 'Link must start with http:// or https://',
      details: { field: 'link' },
    })
  })

  it('ac7_4 keeps the code of a 409', async () => {
    stubFetch(json(409, { error: { code: 'invalid_transition', message: 'Already applied', details: {} } }))
    await expect(api.changeStatus('a1', { status: 'applied' })).rejects.toMatchObject({
      status: 409,
      code: 'invalid_transition',
    })
  })

  it('ac7_9 returns the events, follow-ups and funnel as sent', async () => {
    const events = [{ id: 'e1', application_id: 'a1', from_status: null, to_status: 'saved', note: null, created_at: 'x' }]
    stubFetch(json(200, events))
    await expect(api.listEvents('a1')).resolves.toEqual(events)

    const followups = [{ id: 'a2', company: 'Bluefin Robotics', follow_up_date: '2026-11-10' }]
    stubFetch(json(200, followups))
    await expect(api.listFollowups()).resolves.toEqual(followups)

    const funnel = { total: 0, by_status: { saved: 0 }, by_source: [{ source: 'cold', applied: 0, reached_screen: 0, screen_rate: null }] }
    stubFetch(json(200, funnel))
    await expect(api.getFunnel()).resolves.toEqual(funnel)
  })

  it('ac7_4 keeps the validation message of a status change', async () => {
    stubFetch(json(422, { error: { code: 'validation_error', message: 'Note must be at most 500 characters', details: { field: 'note' } } }))
    await expect(api.changeStatus('a1', { status: 'screen', note: 'x'.repeat(501) })).rejects.toMatchObject({
      status: 422,
      code: 'validation_error',
      message: 'Note must be at most 500 characters',
    })
  })

  it('reports a backend that is not running (proxy 502)', async () => {
    stubFetch(new Response('', { status: 502, statusText: 'Bad Gateway' }))
    await expect(api.listApplications()).rejects.toMatchObject({ code: 'network_error', message: /backend running/ })
  })

  it('reports a network failure', async () => {
    stubFetch(new TypeError('Failed to fetch'))
    await expect(api.listApplications()).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('falls back to internal_error for a non-JSON server error', async () => {
    stubFetch(new Response('oops', { status: 500, statusText: 'Internal Server Error' }))
    await expect(api.listApplications()).rejects.toMatchObject({ status: 500, code: 'internal_error', details: {} })
  })
})
