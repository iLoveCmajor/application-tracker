import { useEffect, useState } from 'react'
import { api, errorMessage, STATUSES, type Application, type Status } from '../api'
import { PageMessage } from '../components/PageMessage'
import { StatusBadge } from '../components/StatusBadge'
import { formatDate, SOURCE_LABELS, STATUS_LABELS } from '../lib/format'
import { href, isStatus, navigate } from '../lib/route'

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; items: Application[] }

export function ApplicationsPage({ status }: { status: Status | null }) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    setState({ kind: 'loading' })
    api
      .listApplications(status ? { status } : undefined)
      .then((items) => current && setState({ kind: 'ready', items }))
      .catch((e: unknown) => current && setState({ kind: 'error', message: errorMessage(e) }))
    return () => {
      current = false
    }
  }, [status, reload])

  return (
    <section className="page">
      <div className="page-header">
        <h1>Applications</h1>
        <div className="page-actions">
          <label className="filter">
            <span>Status</span>
            <select
              value={status ?? ''}
              onChange={(e) => navigate(href.list(isStatus(e.target.value) ? e.target.value : null))}
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <a className="button primary" href={href.new()}>
            New application
          </a>
        </div>
      </div>

      {state.kind === 'loading' && <PageMessage>Loading…</PageMessage>}
      {state.kind === 'error' && (
        <PageMessage tone="error">
          <p>{state.message}</p>
          <button type="button" className="button" onClick={() => setReload((n) => n + 1)}>
            Try again
          </button>
        </PageMessage>
      )}
      {state.kind === 'ready' && state.items.length === 0 && (
        <PageMessage>
          {status ? (
            <p>
              No applications with status <strong>{STATUS_LABELS[status]}</strong>.{' '}
              <a href={href.list(null)}>Show all</a>
            </p>
          ) : (
            <p>
              No applications yet. <a href={href.new()}>Add the first one</a>.
            </p>
          )}
        </PageMessage>
      )}
      {state.kind === 'ready' && state.items.length > 0 && <ApplicationsTable items={state.items} />}
    </section>
  )
}

function ApplicationsTable({ items }: { items: Application[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Role</th>
            <th>Source</th>
            <th>Status</th>
            <th>Applied</th>
            <th>Follow-up</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {items.map((app) => (
            <tr key={app.id}>
              <td className="strong">
                {app.link ? (
                  <a href={app.link} target="_blank" rel="noreferrer" title="Open the posting">
                    {app.company}
                  </a>
                ) : (
                  app.company
                )}
              </td>
              <td>{app.role}</td>
              <td>{SOURCE_LABELS[app.source]}</td>
              <td>
                <StatusBadge status={app.status} />
              </td>
              <td className="nowrap">{formatDate(app.applied_date)}</td>
              <td className="nowrap">{formatDate(app.follow_up_date)}</td>
              <td className="row-actions">
                <a className="button subtle small" href={href.edit(app.id)} aria-label={`Edit ${app.company}`}>
                  Edit
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
