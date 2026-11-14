import type { Status } from '../api'
import { STATUS_LABELS } from '../lib/format'

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABELS[status]}</span>
}
