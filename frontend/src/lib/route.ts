// Hash routing without a router library. Every view has a URL, so a reload keeps it.
//
//   #/                         applications list (optionally #/?status=applied)
//   #/new                      create form
//   #/applications/<id>/edit   edit form
//   #/followups                follow-ups (#7)
//   #/funnel                   funnel (#7)
//
// Anything else shows the list.

import { STATUSES, type Status } from '../api'

export type Route =
  | { name: 'list'; status: Status | null }
  | { name: 'new' }
  | { name: 'edit'; id: string }
  | { name: 'followups' }
  | { name: 'funnel' }

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, '')
  const [path, query = ''] = raw.split('?', 2)
  const clean = path.replace(/\/+$/, '') || '/'

  if (clean === '/new') return { name: 'new' }
  if (clean === '/followups') return { name: 'followups' }
  if (clean === '/funnel') return { name: 'funnel' }

  const edit = /^\/applications\/([^/]+)\/edit$/.exec(clean)
  if (edit) return { name: 'edit', id: decodeURIComponent(edit[1]) }

  const status = new URLSearchParams(query).get('status')
  return { name: 'list', status: isStatus(status) ? status : null }
}

export function isStatus(value: string | null): value is Status {
  return value !== null && (STATUSES as readonly string[]).includes(value)
}

export const href = {
  list: (status?: Status | null) => (status ? `#/?status=${status}` : '#/'),
  new: () => '#/new',
  edit: (id: string) => `#/applications/${encodeURIComponent(id)}/edit`,
  followups: () => '#/followups',
  funnel: () => '#/funnel',
}

export function navigate(to: string): void {
  window.location.hash = to
}
