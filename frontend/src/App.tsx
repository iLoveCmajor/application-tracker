import { useEffect, useState } from 'react'
import { href, parseRoute, type Route } from './lib/route'
import { ApplicationFormPage } from './pages/ApplicationFormPage'
import { ApplicationsPage } from './pages/ApplicationsPage'
import { ApplicationDetailPage } from './pages/ApplicationDetailPage'
import { FollowupsPage } from './pages/FollowupsPage'
import { FunnelPage } from './pages/FunnelPage'

function useRoute(): Route {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return parseRoute(hash)
}

// The detail view opens from a row, so it has no entry of its own in the nav.
const NAV: { label: string; href: string; active: (r: Route) => boolean }[] = [
  {
    label: 'Applications',
    href: href.list(),
    active: (r) => r.name === 'list' || r.name === 'detail' || r.name === 'edit',
  },
  { label: 'New application', href: href.new(), active: (r) => r.name === 'new' },
  { label: 'Follow-ups', href: href.followups(), active: (r) => r.name === 'followups' },
  { label: 'Funnel', href: href.funnel(), active: (r) => r.name === 'funnel' },
]

export function App() {
  const route = useRoute()
  // A link to the page you are already on doesn't change the hash, so nothing would refetch.
  // Bumping this remounts the view instead, which reloads its data.
  const [visit, setVisit] = useState(0)
  const revisit = (to: string) => () => {
    if (sameHash(to, window.location.hash)) setVisit((n) => n + 1)
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <a href={href.list()} className="brand" onClick={revisit(href.list())}>
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
                onClick={revisit(item.href)}
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
        <View key={visit} route={route} />
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
    case 'detail':
      return <ApplicationDetailPage key={route.id} id={route.id} />
    case 'edit':
      return <ApplicationFormPage key={route.id} id={route.id} />
    case 'followups':
      return <FollowupsPage />
    case 'funnel':
      return <FunnelPage />
  }
}

/** `#/` and an empty hash are the same page. */
function sameHash(a: string, b: string): boolean {
  const norm = (h: string) => (h === '' || h === '#' ? '#/' : h)
  return norm(a) === norm(b)
}
