// Shapes mirror openapi.yaml at the repo root. Dates are `YYYY-MM-DD`; timestamps are ISO 8601 in UTC.

export const STATUSES = ['saved', 'applied', 'screen', 'interview', 'offer', 'rejected', 'ghosted'] as const
export type Status = (typeof STATUSES)[number]

export const SOURCES = ['cold', 'inbound', 'referral'] as const
export type Source = (typeof SOURCES)[number]

export interface Application {
  id: string
  company: string
  role: string
  link: string | null
  source: Source
  status: Status
  /** YYYY-MM-DD */
  applied_date: string | null
  /** YYYY-MM-DD */
  follow_up_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** POST /applications. No `status`: a new application starts at `saved`. */
export interface ApplicationInput {
  company: string
  role: string
  link?: string | null
  source: Source
  notes?: string | null
}

/** PATCH /applications/{id}. Every field optional; `null` clears the nullable ones. No `status` (FR-3). */
export interface ApplicationPatch {
  company?: string
  role?: string
  link?: string | null
  source?: Source
  applied_date?: string | null
  follow_up_date?: string | null
  notes?: string | null
}

export interface StatusChange {
  status: Status
  note?: string | null
}

export interface StatusEvent {
  id: string
  application_id: string
  /** `null` for the event written on create */
  from_status: Status | null
  to_status: Status
  note: string | null
  created_at: string
}

export interface SourceFunnel {
  source: Source
  applied: number
  reached_screen: number
  /** reached_screen / applied, 3 decimals; `null` when applied is 0 */
  screen_rate: number | null
}

export interface Funnel {
  total: number
  by_status: Record<Status, number>
  by_source: SourceFunnel[]
}

/** Every backend call the frontend makes. */
export interface Api {
  health(): Promise<{ status: 'ok'; version: string }>
  ready(): Promise<{ status: 'ok' }>

  listApplications(filter?: { status?: Status }): Promise<Application[]>
  createApplication(input: ApplicationInput): Promise<Application>
  getApplication(id: string): Promise<Application>
  updateApplication(id: string, patch: ApplicationPatch): Promise<Application>
  deleteApplication(id: string): Promise<void>
  changeStatus(id: string, change: StatusChange): Promise<Application>
  listEvents(id: string): Promise<StatusEvent[]>

  listFollowups(): Promise<Application[]>
  getFunnel(): Promise<Funnel>
}
