import { useEffect, useState } from 'react'
import { api, errorMessage, type Application } from '../api'
import { PageMessage } from '../components/PageMessage'
import { StatusBadge } from '../components/StatusBadge'
import { isOverdue, todayUtc } from '../lib/dates'
import { formatDate } from '../lib/format'
import { href, navigate } from '../lib/route'

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; items: Application[] }

/** FR-7: applications due a follow-up today or earlier, in the API's order; overdue dates highlighted. */
export function FollowupsPage() {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    setState({ kind: 'loading' })
    api
      .listFollowups()
      .then((items) => current && setState({ kind: 'ready', items }))
      .catch((e: unknown) => current && setState({ kind: 'error', message: errorMessage(e) }))
    return () => {
      current = false
    }
  }, [reload])

  const today = todayUtc()

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <h1>Follow-ups</h1>
          <p className="subtitle">
            Applied, Screen or Interview with a follow-up date of today ({formatDate(today)}, UTC) or earlier.
          </p>
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
          <p>Nothing to follow up today.</p>
        </PageMessage>
      )}
      {state.kind === 'ready' && state.items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Follow-up</th>
                <th>Company</th>
                <th>Role</th>
                <th>Status</th>
                <th>Applied</th>
              </tr>
            </thead>
            <tbody>
              {state.items.map((app) => {
                const overdue = isOverdue(app.follow_up_date, today)
                return (
                  <tr
                    key={app.id}
                    className="clickable"
                    onClick={() => navigate(href.detail(app.id))}
                  >
                    <td className="nowrap">
                      <span className={overdue ? 'due overdue' : 'due'}>{formatDate(app.follow_up_date)}</span>
                      {overdue && <span className="overdue-label">Overdue</span>}
                    </td>
                    <td className="strong">
                      <a href={href.detail(app.id)}>{app.company}</a>
                    </td>
                    <td>{app.role}</td>
                    <td>
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="nowrap">{formatDate(app.applied_date)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
