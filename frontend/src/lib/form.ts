// Form values are plain strings; these turn them into the API's create and patch bodies.
// No validation here on purpose: the server is the single source of the rules and its
// message is shown next to the form.

import type { Application, ApplicationInput, ApplicationPatch, Source } from '../api'

export interface FormValues {
  company: string
  role: string
  link: string
  source: Source
  notes: string
  applied_date: string
  follow_up_date: string
}

export const EMPTY_FORM: FormValues = {
  company: '',
  role: '',
  link: '',
  source: 'cold',
  notes: '',
  applied_date: '',
  follow_up_date: '',
}

export function valuesFrom(app: Application): FormValues {
  return {
    company: app.company,
    role: app.role,
    link: app.link ?? '',
    source: app.source,
    notes: app.notes ?? '',
    applied_date: app.applied_date ?? '',
    follow_up_date: app.follow_up_date ?? '',
  }
}

const orNull = (value: string) => (value.trim() === '' ? null : value)

/** Create body: no status, no dates; empty optional fields are left out. */
export function toInput(values: FormValues): ApplicationInput {
  const input: ApplicationInput = { company: values.company, role: values.role, source: values.source }
  const link = orNull(values.link)
  const notes = orNull(values.notes)
  if (link !== null) input.link = link
  if (notes !== null) input.notes = notes
  return input
}

/** Patch body: only the fields that changed; a cleared optional field is sent as `null`. */
export function toPatch(original: Application, values: FormValues): ApplicationPatch {
  const patch: ApplicationPatch = {}
  if (values.company !== original.company) patch.company = values.company
  if (values.role !== original.role) patch.role = values.role
  if (values.source !== original.source) patch.source = values.source
  for (const key of ['link', 'notes', 'applied_date', 'follow_up_date'] as const) {
    const next = orNull(values[key])
    if (next !== original[key]) patch[key] = next
  }
  return patch
}
