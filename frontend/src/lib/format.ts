import type { Source, Status } from '../api'

export const STATUS_LABELS: Record<Status, string> = {
  saved: 'Saved',
  applied: 'Applied',
  screen: 'Screen',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
  ghosted: 'Ghosted',
}

export const SOURCE_LABELS: Record<Source, string> = {
  cold: 'Cold',
  inbound: 'Inbound',
  referral: 'Referral',
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** `2026-11-04` → `4 Nov 2026`. Parsed by hand so the browser's time zone can't shift the day. */
export function formatDate(value: string | null): string {
  if (!value) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return value
  const month = MONTHS[Number(m[2]) - 1]
  return month ? `${Number(m[3])} ${month} ${m[1]}` : value
}

/** `2026-11-04T14:05:09Z` → `4 Nov 2026, 14:05 UTC`. UTC, like the server's dates. */
export function formatTimestamp(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const iso = d.toISOString()
  return `${formatDate(iso.slice(0, 10))}, ${iso.slice(11, 16)} UTC`
}

/** A funnel rate as a percentage: 0.333 → `33.3%`, 1 → `100%`, 0 → `0%`, null (nothing applied) → `n/a`. */
export function formatRate(rate: number | null): string {
  if (rate === null || !Number.isFinite(rate)) return 'n/a'
  return `${Number((rate * 100).toFixed(1))}%`
}
