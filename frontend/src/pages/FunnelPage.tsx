import { useEffect, useState } from 'react'
import { api, errorMessage, STATUSES, type Funnel } from '../api'
import { PageMessage } from '../components/PageMessage'
import { StatusBadge } from '../components/StatusBadge'
import { formatRate, SOURCE_LABELS } from '../lib/format'

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; funnel: Funnel }

/** FR-8: a count per status, and per source how many reached Applied and Screen with the rate between them. */
export function FunnelPage() {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    setState({ kind: 'loading' })
    api
      .getFunnel()
      .then((funnel) => current && setState({ kind: 'ready', funnel }))
      .catch((e: unknown) => current && setState({ kind: 'error', message: errorMessage(e) }))
    return () => {
      current = false
    }
  }, [reload])

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <h1>Funnel</h1>
          {state.kind === 'ready' && (
            <p className="subtitle">
              {state.funnel.total} application{state.funnel.total === 1 ? '' : 's'} in total.
            </p>
          )}
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
      {state.kind === 'ready' && (
        <>
          <h2 className="section-title">By status</h2>
          <ul className="status-counts">
            {STATUSES.map((s) => (
              <li key={s} className="card">
                <StatusBadge status={s} />
                <span className="count">{state.funnel.by_status[s] ?? 0}</span>
              </li>
            ))}
          </ul>

          <h2 className="section-title">By source</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th className="num">Applied</th>
                  <th className="num">Reached screen</th>
                  <th className="num">Screen rate</th>
                </tr>
              </thead>
              <tbody>
                {state.funnel.by_source.map((row) => (
                  <tr key={row.source}>
                    <td className="strong">{SOURCE_LABELS[row.source]}</td>
                    <td className="num">{row.applied}</td>
                    <td className="num">{row.reached_screen}</td>
                    <td className="num">{formatRate(row.screen_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint-text">Screen rate is reached screen divided by applied; n/a when nothing was applied.</p>
        </>
      )}
    </section>
  )
}
