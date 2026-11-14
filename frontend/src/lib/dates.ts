// "Today" in the UI is the UTC date, the same day the server uses for follow-ups (FR-7).

/** The UTC date as `YYYY-MM-DD`. */
export function todayUtc(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10)
}

/** A follow-up date is overdue when it is strictly before `today`. Both are `YYYY-MM-DD`. */
export function isOverdue(date: string | null, today: string): boolean {
  return date !== null && date < today
}
