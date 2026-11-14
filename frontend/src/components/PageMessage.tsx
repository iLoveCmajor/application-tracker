import type { ReactNode } from 'react'

/** A centred message for loading, empty and error states. */
export function PageMessage({ tone = 'muted', children }: { tone?: 'muted' | 'error'; children: ReactNode }) {
  return (
    <div className={`page-message ${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {children}
    </div>
  )
}
