import type { ReactNode } from 'react'

/** Stands in for a view that a later issue builds (follow-ups and funnel: #7). */
export function PlaceholderPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="page">
      <div className="page-header">
        <h1>{title}</h1>
      </div>
      <div className="placeholder card">
        <span className="badge">Coming in #7</span>
        <p>{children}</p>
      </div>
    </section>
  )
}
