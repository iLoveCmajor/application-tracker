import { useEffect, useState } from 'react'
import { href, parseRoute, type Route } from './lib/route'
import { ApplicationFormPage } from './pages/ApplicationFormPage'
import { ApplicationsPage } from './pages/ApplicationsPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

function useRoute(): Route {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return parseRoute(hash)
}

// The detail view (#7) opens from a row, so it has no entry of its own in the nav.
const NAV: { label: string; href: string; active: (r: Route) => boolean }[] = [
  {
    label: 'Applications',
    href: href.list(),
    active: (r) => r.name === 'list' || r.name === 'edit',
  },
  { label: 'New application', href: href.new(), active: (r) => r.name === 'new' },
  { label: 'Follow-ups', href: href.followups(), active: (r) => r.name === 'followups' },
  { label: 'Funnel', href: href.funnel(), active: (r) => r.name === 'funnel' },
]

export function App() {
  const route = useRoute()

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <a href={href.list()} className="brand">
            <span className="brand-mark" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            Application Tracker
          </a>
          <nav className="nav" aria-label="Main">
            {NAV.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className={item.active(route) ? 'nav-link active' : 'nav-link'}
                aria-current={item.active(route) ? 'page' : undefined}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className="main">
        <View route={route} />
      </main>
    </div>
  )
}

function View({ route }: { route: Route }) {
  switch (route.name) {
    case 'list':
      return <ApplicationsPage status={route.status} />
    case 'new':
      return <ApplicationFormPage key="new" />
    case 'edit':
      return <ApplicationFormPage key={route.id} id={route.id} />
    case 'followups':
      return (
        <PlaceholderPage title="Follow-ups">
          Applications in Applied, Screen or Interview whose follow-up date is today or earlier, overdue dates
          highlighted.
        </PlaceholderPage>
      )
    case 'funnel':
      return (
        <PlaceholderPage title="Funnel">
          A count per status, and per source how many applications reached Applied and Screen, with the rate as a
          percentage.
        </PlaceholderPage>
      )
  }
}
