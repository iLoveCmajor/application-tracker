import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError, errorMessage, STATUSES, type Application, type Status, type StatusEvent } from '../api'
import { PageMessage } from '../components/PageMessage'
import { StatusBadge } from '../components/StatusBadge'
import { formatDate, formatTimestamp, SOURCE_LABELS, STATUS_LABELS } from '../lib/format'
import { href, navigate } from '../lib/route'

type Load =
  | { kind: 'loading' }
  | { kind: 'not_found' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; app: Application; events: StatusEvent[] }

/** One application: every field, the status change, the history, edit and delete. */
export function ApplicationDetailPage({ id }: { id: string }) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    setLoad({ kind: 'loading' })
    Promise.all([api.getApplication(id), api.listEvents(id)])
      .then(([app, events]) => current && setLoad({ kind: 'ready', app, events }))
      .catch((e: unknown) => {
        if (!current) return
        if (e instanceof ApiError && e.code === 'not_found') setLoad({ kind: 'not_found' })
        else setLoad({ kind: 'error', message: errorMessage(e) })
      })
    return () => {
      current = false
    }
  }, [id, reload])

  if (load.kind === 'loading') return <PageMessage>Loading…</PageMessage>
  if (load.kind === 'not_found')
    return (
      <PageMessage>
        <p>Application not found. It may have been deleted.</p>
        <a href={href.list()}>Back to applications</a>
      </PageMessage>
    )
  if (load.kind === 'error')
    return (
      <PageMessage tone="error">
        <p>{load.message}</p>
        <button type="button" className="button" onClick={() => setReload((n) => n + 1)}>
          Try again
        </button>
      </PageMessage>
    )

  return (
    <Detail
      app={load.app}
      events={load.events}
      onChanged={(app, events) => setLoad({ kind: 'ready', app, events })}
    />
  )
}

function Detail({
  app,
  events,
  onChanged,
}: {
  app: Application
  events: StatusEvent[]
  onChanged: (app: Application, events: StatusEvent[]) => void
}) {
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function remove() {
    if (!window.confirm(`Delete the application to ${app.company}? Its history goes too.`)) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.deleteApplication(app.id)
      navigate(href.list())
    } catch (e) {
      setDeleteError(errorMessage(e))
      setDeleting(false)
    }
  }

  return (
    <section className="page narrow">
      <div className="page-header">
        <div>
          <a className="back-link" href={href.list()}>
            ← Applications
          </a>
          <h1>{app.company}</h1>
          <p className="subtitle">{app.role}</p>
        </div>
        <div className="page-actions">
          <a className="button" href={href.edit(app.id)}>
            Edit
          </a>
          <button type="button" className="button danger" onClick={remove} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {deleteError && (
        <div className="form-error spaced" role="alert">
          {deleteError}
        </div>
      )}

      <div className="card details">
        <dl className="fields">
          <Item label="Status">
            <StatusBadge status={app.status} />
          </Item>
          <Item label="Source">{SOURCE_LABELS[app.source]}</Item>
          <Item label="Applied">{formatDate(app.applied_date)}</Item>
          <Item label="Follow-up">{formatDate(app.follow_up_date)}</Item>
          <Item label="Link" wide>
            {app.link ? (
              <a href={app.link} target="_blank" rel="noreferrer" className="break">
                {app.link}
              </a>
            ) : (
              '—'
            )}
          </Item>
          <Item label="Notes" wide>
            {app.notes ? <span className="pre">{app.notes}</span> : '—'}
          </Item>
          <Item label="Created">{formatTimestamp(app.created_at)}</Item>
          <Item label="Updated">{formatTimestamp(app.updated_at)}</Item>
        </dl>
      </div>

      <StatusForm key={app.status} app={app} onChanged={onChanged} />

      <h2 className="section-title">History</h2>
      <History events={events} />
    </section>
  )
}

function Item({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <div className={wide ? 'item wide' : 'item'}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function StatusForm({
  app,
  onChanged,
}: {
  app: Application
  onChanged: (app: Application, events: StatusEvent[]) => void
}) {
  const [status, setStatus] = useState<Status>(app.status)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const trimmed = note.trim()
      const updated = await api.changeStatus(app.id, { status, note: trimmed ? note : null })
      const events = await api.listEvents(app.id)
      onChanged(updated, events)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <form className="card status-form" onSubmit={submit} noValidate>
      <h2 className="section-title">Change status</h2>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      <div className="status-row">
        <div className="field">
          <label htmlFor="new-status">New status</label>
          <select id="new-status" value={status} onChange={(e) => setStatus(e.target.value as Status)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
                {s === app.status ? ' (current)' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="field grow">
          <label htmlFor="status-note">Note</label>
          <input
            id="status-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional, up to 500 characters"
          />
        </div>
        <button type="submit" className="button primary" disabled={saving}>
          {saving ? 'Saving…' : 'Change status'}
        </button>
      </div>
    </form>
  )
}

function History({ events }: { events: StatusEvent[] }) {
  if (events.length === 0) return <PageMessage>No history.</PageMessage>
  return (
    <ol className="history card">
      {events.map((ev) => (
        <li key={ev.id}>
          <div className="history-change">
            {ev.from_status ? (
              <>
                <StatusBadge status={ev.from_status} /> <span aria-label="to">→</span>{' '}
                <StatusBadge status={ev.to_status} />
              </>
            ) : (
              <>
                <span className="muted">Created</span> <span aria-label="as">→</span>{' '}
                <StatusBadge status={ev.to_status} />
              </>
            )}
          </div>
          <time className="muted small" dateTime={ev.created_at}>
            {formatTimestamp(ev.created_at)}
          </time>
          {ev.note && <p className="history-note pre">{ev.note}</p>}
        </li>
      ))}
    </ol>
  )
}
