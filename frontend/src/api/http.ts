import { ApiError, type ErrorCode } from './errors'
import type { Api } from './types'

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

const UNREACHABLE = 'Could not reach the server. Is the backend running?'

/**
 * `apiBase` is where /applications, /followups and /stats live (normally `/api/v1`);
 * `rootBase` is where /health and /ready live (the same origin, outside /api/v1).
 */
export function createHttpApi(apiBase: string, rootBase = ''): Api {
  async function request<T>(method: Method, url: string, body?: unknown): Promise<T> {
    let res: Response
    try {
      res = await fetch(url, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch {
      throw new ApiError(0, 'network_error', UNREACHABLE)
    }
    if (res.status === 204) return undefined as T

    const data: unknown = await res.json().catch(() => null)
    if (!res.ok) {
      const err = (data as { error?: { code?: ErrorCode; message?: string; details?: Record<string, unknown> } } | null)
        ?.error
      // No error body from a gateway status means the backend itself didn't answer
      // (e.g. the dev server proxy returns 502 when nothing listens on :8000).
      if (!err && res.status >= 502 && res.status <= 504) throw new ApiError(res.status, 'network_error', UNREACHABLE)
      throw new ApiError(res.status, err?.code ?? 'internal_error', err?.message ?? res.statusText, err?.details)
    }
    return data as T
  }

  const api = <T>(method: Method, path: string, body?: unknown) => request<T>(method, apiBase + path, body)
  const id = encodeURIComponent

  return {
    health: () => request('GET', `${rootBase}/health`),
    ready: () => request('GET', `${rootBase}/ready`),

    listApplications: (filter) =>
      api('GET', filter?.status ? `/applications?status=${id(filter.status)}` : '/applications'),
    createApplication: (input) => api('POST', '/applications', input),
    getApplication: (appId) => api('GET', `/applications/${id(appId)}`),
    updateApplication: (appId, patch) => api('PATCH', `/applications/${id(appId)}`, patch),
    deleteApplication: (appId) => api('DELETE', `/applications/${id(appId)}`),
    changeStatus: (appId, change) => api('POST', `/applications/${id(appId)}/status`, change),
    listEvents: (appId) => api('GET', `/applications/${id(appId)}/events`),

    listFollowups: () => api('GET', '/followups'),
    getFunnel: () => api('GET', '/stats/funnel'),
  }
}
