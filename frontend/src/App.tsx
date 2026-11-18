import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  ChevronRight,
  Dna,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  Microscope,
  ShieldCheck,
  Users,
  UserRoundCog,
  X,
} from 'lucide-react'
import { api, body, TOKEN_KEY } from './api'
import { Alert, Badge, Empty, Field, Loading, useLoad } from './ui'
import {
  date,
  label,
  roleLabel,
  states,
  type Page,
  type Participant,
  type Phenotype,
  type Summary,
  type User,
} from './types'
import Participants from './Participants'
import Samples from './Samples'
import Phenotypes from './Phenotypes'
import { Accounts, AuditLog } from './Admin'

type Screen = 'overview' | 'participants' | 'samples' | 'phenotypes' | 'audit' | 'accounts'
const navigation = [
  {
    id: 'overview',
    title: 'Overview',
    icon: LayoutDashboard,
    roles: ['admin', 'lab_tech', 'field_officer'],
  },
  {
    id: 'participants',
    title: 'Participants',
    icon: Users,
    roles: ['admin', 'lab_tech', 'field_officer'],
  },
  {
    id: 'samples',
    title: 'Samples & sequencing',
    icon: FlaskConical,
    roles: ['admin', 'lab_tech', 'field_officer'],
  },
  {
    id: 'phenotypes',
    title: 'Phenotype records',
    icon: Activity,
    roles: ['admin', 'field_officer'],
  },
  { id: 'audit', title: 'Audit log', icon: ShieldCheck, roles: ['admin'] },
  { id: 'accounts', title: 'Team accounts', icon: UserRoundCog, roles: ['admin'] },
]

function Login({ signedIn, notice }: { signedIn: (user: User) => void; notice: string }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api<{ access_token: string; user: User }>('/auth/login', {
        method: 'POST',
        body: body({ username, password }),
      })
      sessionStorage.setItem(TOKEN_KEY, result.access_token)
      signedIn(result.user)
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="login-page">
      <aside className="login-story">
        <a href="#" className="brand">
          <span className="brand-mark">
            <Dna size={28} />
          </span>
          <span>
            KGRI<small>PARTICIPANT PORTAL</small>
          </span>
        </a>
        <div className="login-story-copy">
          <span className="login-kicker">KENYA GENOME REFERENCE INITIATIVE</span>
          <h1>
            Better research.
            <br />
            <em>Connected care.</em>
          </h1>
          <p>
            A shared workspace for participant registration, sample tracking, and health
            observations.
          </p>
          <div className="login-pill">
            <span />
            Research operations
          </div>
        </div>
        <div className="login-pattern" aria-hidden="true">
          <div />
          <div />
          <div />
          <div />
          <div />
          <div />
          <div />
        </div>
        <footer>
          <Dna size={18} />
          <span>CMB Genomics · Kenya</span>
        </footer>
      </aside>
      <main className="login-main">
        <div className="login-card">
          <div className="login-mobile-brand">
            <Dna size={30} />
            <strong>KGRI</strong>
          </div>
          <div className="eyebrow">YOUR RESEARCH WORKSPACE</div>
          <h2>Welcome back.</h2>
          <p>Sign in to the KGRI Participant Portal.</p>
          <Alert>{error || notice}</Alert>
          <form onSubmit={submit}>
            <Field label="Username">
              <input
                id="username"
                aria-label="Username"
                autoComplete="username"
                required
                autoFocus
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter your username"
              />
            </Field>
            <Field label="Password">
              <input
                id="password"
                aria-label="Password"
                autoComplete="current-password"
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
              />
            </Field>
            <button className="button primary login-submit" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
              <ArrowRight size={18} />
            </button>
          </form>
          <div className="login-help">
            <ShieldCheck size={18} />
            <p>
              Use the account provided by your administrator.
              <br />
              Access is based on your assigned role.
            </p>
          </div>
        </div>
        <footer>Kenya Genome Reference Initiative</footer>
      </main>
    </div>
  )
}

function Overview({ user, navigate }: { user: User; navigate: (screen: Screen) => void }) {
  const summary = useLoad(() => api<Summary>('/samples/summary'), [])
  const participants = useLoad(() => api<Page<Participant>>('/participants?page_size=5'), [])
  const consented = useLoad(
    () => api<Page<Participant>>('/participants?page_size=1&broad_consent=true'),
    [],
  )
  const phenotypes = useLoad(
    () =>
      user.role === 'lab_tech'
        ? Promise.resolve(undefined)
        : api<Page<Phenotype>>('/phenotypes?page_size=1'),
    [user.role],
  )
  const total = summary.data?.total || 0
  const completed = summary.data?.by_status.find((item) => item.status === 'qc_passed')?.count || 0
  const percent = total ? Math.round((completed / total) * 100) : 0
  const chartMax = Math.max(1, ...(summary.data?.by_status.map((item) => item.count) || []))
  const siteMax = Math.max(1, ...(summary.data?.by_site.map((item) => item.count) || []))
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">KGRI RESEARCH OPERATIONS</div>
          <h1>
            Workspace overview<span className="heading-dot">.</span>
          </h1>
          <p>Participant care and research progress, in one place.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => navigate(user.role === 'lab_tech' ? 'samples' : 'participants')}
        >
          {user.role === 'lab_tech' ? <FlaskConical size={17} /> : <Users size={17} />}
          {user.role === 'lab_tech' ? 'View sample register' : 'View participant registry'}
          <ArrowUpRight size={16} />
        </button>
      </div>
      <Alert>{participants.error || summary.error || consented.error || phenotypes.error}</Alert>
      <div className="stat-grid">
        <button className="stat-card" onClick={() => navigate('participants')}>
          <div className="stat-top">
            <span>Registered participants</span>
            <Users size={19} />
          </div>
          <strong>
            {participants.loading ? '—' : (participants.data?.total.toLocaleString() ?? '—')}
          </strong>
          <div className="stat-bottom">
            <span>Active participant records</span>
            <ArrowUpRight size={16} />
          </div>
        </button>
        <button className="stat-card" onClick={() => navigate('samples')}>
          <div className="stat-top">
            <span>Samples tracked</span>
            <FlaskConical size={19} />
          </div>
          <strong>{summary.loading ? '—' : (summary.data?.total.toLocaleString() ?? '—')}</strong>
          <div className="stat-bottom">
            <span>Across the sample journey</span>
            <ArrowUpRight size={16} />
          </div>
        </button>
        <button className="stat-card" onClick={() => navigate('participants')}>
          <div className="stat-top">
            <span>Broad research consent</span>
            <ShieldCheck size={19} />
          </div>
          <strong>
            {consented.loading ? '—' : (consented.data?.total.toLocaleString() ?? '—')}
          </strong>
          <div className="stat-bottom">
            <span>Participants who granted consent</span>
            <ArrowUpRight size={16} />
          </div>
        </button>
        <button
          className="stat-card accent"
          onClick={() => navigate(user.role === 'lab_tech' ? 'samples' : 'phenotypes')}
        >
          <div className="stat-top">
            <span>{user.role === 'lab_tech' ? 'Quality control passed' : 'Phenotype records'}</span>
            {user.role === 'lab_tech' ? <CheckCheck size={19} /> : <Activity size={19} />}
          </div>
          <strong>
            {user.role === 'lab_tech'
              ? summary.loading
                ? '—'
                : completed.toLocaleString()
              : phenotypes.loading
                ? '—'
                : (phenotypes.data?.total.toLocaleString() ?? '—')}
          </strong>
          <div className="stat-bottom">
            <span>
              {user.role === 'lab_tech'
                ? `${percent}% of tracked samples`
                : 'Health observations captured'}
            </span>
            <ArrowUpRight size={16} />
          </div>
        </button>
      </div>
      <div className="dashboard-grid">
        <section className="panel pipeline-panel">
          <div className="panel-title">
            <div>
              <h2>Sample pipeline</h2>
              <p>Current position of active samples</p>
            </div>
            <Badge>{total} samples</Badge>
          </div>
          {summary.loading ? (
            <Loading />
          ) : (
            <div className="pipeline-chart">
              {states.map((status, index) => {
                const count =
                  summary.data?.by_status.find((item) => item.status === status)?.count || 0
                return (
                  <div className="pipeline-row" key={status}>
                    <span>
                      <i className={count ? 'has-count' : ''}>{index + 1}</i>
                      {label(status)}
                    </span>
                    <div className="bar-track">
                      <div
                        className={status === 'qc_passed' ? 'bar completed' : 'bar'}
                        style={{ width: `${(count / chartMax) * 100}%` }}
                      />
                    </div>
                    <strong>{count}</strong>
                  </div>
                )
              })}
            </div>
          )}
          <div className="panel-foot">
            <span>
              <i className="legend-dot" />
              Sequential sample workflow
            </span>
            <button className="text-button" onClick={() => navigate('samples')}>
              Open samples
              <ArrowRight size={15} />
            </button>
          </div>
        </section>
        <section className="panel sites-panel">
          <div className="panel-title">
            <div>
              <h2>Recruitment sites</h2>
              <p>Sample distribution by collection site</p>
            </div>
            <Microscope size={20} />
          </div>
          {summary.loading ? (
            <Loading />
          ) : !summary.data?.by_site.length ? (
            <Empty title="No sample sites yet">Sites appear when samples are registered.</Empty>
          ) : (
            <div className="site-list">
              {summary.data.by_site.map((site, index) => (
                <div className="site-row" key={site.recruitment_site}>
                  <div>
                    <span className={`site-marker site-${index % 3}`} />
                    <strong>{site.recruitment_site}</strong>
                    <span>{site.count} samples</span>
                  </div>
                  <div className="site-bar">
                    <div style={{ width: `${(site.count / siteMax) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="site-total">
            <span>QC passed</span>
            <strong>
              {percent}
              <small>%</small>
            </strong>
            <span>
              {completed} of {total} samples
            </span>
          </div>
        </section>
      </div>
      <section className="panel recent-panel">
        <div className="panel-title">
          <div>
            <h2>Recent registrations</h2>
            <p>The latest participants added to the registry</p>
          </div>
          <button className="text-button" onClick={() => navigate('participants')}>
            View all participants
            <ArrowRight size={15} />
          </button>
        </div>
        {participants.loading ? (
          <Loading />
        ) : !participants.data?.items.length ? (
          <Empty title="Your registry is ready">
            Register your first participant to get started.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Participant</th>
                  <th>KGRI ID</th>
                  <th>County</th>
                  <th>Recruitment site</th>
                  <th>Research consent</th>
                  <th>Registered</th>
                </tr>
              </thead>
              <tbody>
                {participants.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="user-cell">
                        <span className="participant-avatar">
                          {item.full_name
                            .split(' ')
                            .map((name) => name[0])
                            .slice(0, 2)
                            .join('')}
                        </span>
                        <strong>{item.full_name}</strong>
                      </div>
                    </td>
                    <td className="mono">{item.kgri_id}</td>
                    <td>{item.county}</td>
                    <td>{item.recruitment_site}</td>
                    <td>
                      <Badge tone={item.consent.broad_consent ? 'green' : ''}>
                        {item.consent.broad_consent ? 'Granted' : 'Not granted'}
                      </Badge>
                    </td>
                    <td className="muted">{date(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <div className="workspace-footnote">
        <ShieldCheck size={15} />
        <span>Role-based access · Changes are recorded in the audit log</span>
        <span>KGRI Participant Portal</span>
      </div>
    </>
  )
}

export default function App() {
  const [user, setUser] = useState<User>()
  const [checking, setChecking] = useState(Boolean(sessionStorage.getItem(TOKEN_KEY)))
  const [notice, setNotice] = useState('')
  const [screen, setScreen] = useState<Screen>((location.hash.slice(1) || 'overview') as Screen)
  const [menu, setMenu] = useState(false)
  useEffect(() => {
    const expired = () => {
      setUser(undefined)
      setNotice('Your session has expired. Please sign in again.')
    }
    window.addEventListener('kgri-session-expired', expired)
    if (sessionStorage.getItem(TOKEN_KEY))
      api<User>('/auth/me')
        .then(setUser)
        .catch((reason) => {
          setNotice((reason as Error).message)
          sessionStorage.removeItem(TOKEN_KEY)
        })
        .finally(() => setChecking(false))
    const hashChanged = () => {
      setScreen((location.hash.slice(1) || 'overview') as Screen)
      setMenu(false)
    }
    window.addEventListener('hashchange', hashChanged)
    return () => {
      window.removeEventListener('kgri-session-expired', expired)
      window.removeEventListener('hashchange', hashChanged)
    }
  }, [])
  const navigate = (target: Screen) => {
    location.hash = target
    setScreen(target)
    setMenu(false)
  }
  const logout = () => {
    sessionStorage.removeItem(TOKEN_KEY)
    setUser(undefined)
    setNotice('')
    navigate('overview')
  }
  if (checking)
    return (
      <div className="app-loading">
        <Dna size={35} />
        <Loading />
      </div>
    )
  if (!user)
    return (
      <Login
        signedIn={(value) => {
          setUser(value)
          setNotice('')
        }}
        notice={notice}
      />
    )
  const available = navigation.filter((item) => item.roles.includes(user.role))
  const selected = available.find((item) => item.id === screen) || available[0]
  const current = selected.id as Screen
  return (
    <div className="app-shell">
      {menu && (
        <button
          className="sidebar-overlay"
          aria-label="Close menu"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? 'open' : ''}`}>
        <a href="#overview" className="brand">
          <span className="brand-mark">
            <Dna size={27} />
          </span>
          <span>
            KGRI<small>PARTICIPANT PORTAL</small>
          </span>
        </a>
        <button
          className="mobile-close icon-button"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        >
          <X size={20} />
        </button>
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {available.map((item) => (
            <button
              key={item.id}
              className={current === item.id ? 'nav-item active' : 'nav-item'}
              onClick={() => navigate(item.id as Screen)}
              aria-current={current === item.id ? 'page' : undefined}
            >
              <item.icon size={19} />
              <span>{item.title}</span>
              {current === item.id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-research">
          <div className="sidebar-research-icon">
            <Dna size={22} />
          </div>
          <strong>Connected research.</strong>
          <p>
            Kenya Genome
            <br />
            Reference Initiative
          </p>
        </div>
        <div className="sidebar-user">
          <span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span>
          <div>
            <strong>{user.username}</strong>
            <small>{roleLabel[user.role]}</small>
          </div>
          <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={logout}>
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">
              Workspace
              <ChevronRight size={14} />
              <strong>{selected.title}</strong>
            </span>
          </div>
          <div className="topbar-right">
            <span className="today">
              {new Date().toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              })}
            </span>
            <span className="role-chip">
              <span />
              {roleLabel[user.role]}
            </span>
          </div>
        </header>
        <main className="main-content">
          {current === 'overview' && <Overview user={user} navigate={navigate} />}
          {current === 'participants' && <Participants role={user.role} />}
          {current === 'samples' && <Samples role={user.role} />}
          {current === 'phenotypes' && <Phenotypes role={user.role} />}
          {current === 'audit' && <AuditLog />}
          {current === 'accounts' && <Accounts currentUser={user} currentUserChanged={setUser} />}
        </main>
        <footer className="app-footer">
          <span>Kenya Genome Reference Initiative</span>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API documentation
            <ArrowDownToLine size={12} />
          </a>
        </footer>
      </div>
    </div>
  )
}
