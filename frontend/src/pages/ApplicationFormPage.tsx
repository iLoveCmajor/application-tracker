import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError, errorMessage, SOURCES, type Application } from '../api'
import { PageMessage } from '../components/PageMessage'
import { EMPTY_FORM, toInput, toPatch, valuesFrom, type FormValues } from '../lib/form'
import { SOURCE_LABELS } from '../lib/format'
import { href, navigate } from '../lib/route'

type Load = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; app: Application | null }

/** Create (no `id`) or edit an application. Creating returns to the list, editing to the application's detail. */
export function ApplicationFormPage({ id }: { id?: string }) {
  const [load, setLoad] = useState<Load>(id ? { kind: 'loading' } : { kind: 'ready', app: null })
  const [values, setValues] = useState<FormValues>(EMPTY_FORM)

  useEffect(() => {
    if (!id) return
    let current = true
    api
      .getApplication(id)
      .then((app) => {
        if (!current) return
        setValues(valuesFrom(app))
        setLoad({ kind: 'ready', app })
      })
      .catch((e: unknown) => current && setLoad({ kind: 'error', message: errorMessage(e) }))
    return () => {
      current = false
    }
  }, [id])

  if (load.kind === 'loading') return <PageMessage>Loading…</PageMessage>
  if (load.kind === 'error')
    return (
      <PageMessage tone="error">
        <p>{load.message}</p>
        <a href={href.list()}>Back to applications</a>
      </PageMessage>
    )

  return <ApplicationForm original={load.app} values={values} onChange={setValues} />
}

function ApplicationForm({
  original,
  values,
  onChange,
}: {
  original: Application | null
  values: FormValues
  onChange: (values: FormValues) => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<{ message: string; field: string | null } | null>(null)
  const editing = original !== null

  const set =
    <K extends keyof FormValues>(key: K) =>
    (e: { target: { value: string } }) =>
      onChange({ ...values, [key]: e.target.value as FormValues[K] })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (original) {
        const patch = toPatch(original, values)
        if (Object.keys(patch).length > 0) await api.updateApplication(original.id, patch)
      } else {
        await api.createApplication(toInput(values))
      }
      navigate(original ? href.detail(original.id) : href.list())
    } catch (err) {
      const field = err instanceof ApiError && typeof err.details.field === 'string' ? err.details.field : null
      setError({ message: errorMessage(err), field })
      setSaving(false)
    }
  }

  const invalid = (name: keyof FormValues) => error?.field === name
  const back = original ? href.detail(original.id) : href.list()

  return (
    <section className="page narrow">
      <div className="page-header">
        <div>
          <a className="back-link" href={back}>
            ← {original ? original.company : 'Applications'}
          </a>
          <h1>{editing ? `Edit ${original.company}` : 'New application'}</h1>
        </div>
      </div>

      <form className="form card" onSubmit={submit} noValidate>
        {error && (
          <div className="form-error" role="alert">
            {error.message}
          </div>
        )}

        <div className="form-row">
          <Field label="Company" name="company" invalid={invalid('company')}>
            <input id="company" name="company" value={values.company} onChange={set('company')} autoFocus />
          </Field>
          <Field label="Role" name="role" invalid={invalid('role')}>
            <input id="role" name="role" value={values.role} onChange={set('role')} />
          </Field>
        </div>

        <div className="form-row">
          <Field label="Link" name="link" hint="Optional, http:// or https://" invalid={invalid('link')}>
            <input
              id="link"
              name="link"
              value={values.link}
              onChange={set('link')}
              placeholder="https://"
              inputMode="url"
            />
          </Field>
          <Field label="Source" name="source" invalid={invalid('source')}>
            <select id="source" name="source" value={values.source} onChange={set('source')}>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABELS[s]}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {editing && (
          <div className="form-row">
            <Field label="Applied date" name="applied_date" invalid={invalid('applied_date')}>
              <input
                id="applied_date"
                name="applied_date"
                type="date"
                value={values.applied_date}
                onChange={set('applied_date')}
              />
            </Field>
            <Field label="Follow-up date" name="follow_up_date" invalid={invalid('follow_up_date')}>
              <input
                id="follow_up_date"
                name="follow_up_date"
                type="date"
                value={values.follow_up_date}
                onChange={set('follow_up_date')}
              />
            </Field>
          </div>
        )}

        <Field label="Notes" name="notes" hint="Optional" invalid={invalid('notes')}>
          <textarea id="notes" name="notes" rows={5} value={values.notes} onChange={set('notes')} />
        </Field>

        <div className="form-actions">
          <a className="button subtle" href={back}>
            Cancel
          </a>
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Create application'}
          </button>
        </div>
      </form>
    </section>
  )
}

function Field({
  label,
  name,
  hint,
  invalid,
  children,
}: {
  label: string
  name: string
  hint?: string
  invalid: boolean
  children: ReactNode
}) {
  return (
    <div className={invalid ? 'field invalid' : 'field'}>
      <label htmlFor={name}>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  )
}
