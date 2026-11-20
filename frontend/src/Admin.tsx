import { useState, type FormEvent } from 'react'
import { ChevronDown, Edit3, Plus, ShieldCheck } from 'lucide-react'
import { api, body, query } from './api'
import { Alert, Badge, Empty, Field, fieldErrors, Loading, Modal, Pagination, useLoad } from './ui'
import {
  dateTime,
  label,
  roleLabel,
  type AuditEvent,
  type Page,
  type Role,
  type User,
} from './types'

export function AuditLog() {
  const [userId, setUserId] = useState('')
  const [entity, setEntity] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<number>()
  const users = useLoad(() => api<User[]>('/auth/users'), [])
  const result = useLoad(
    () =>
      api<Page<AuditEvent>>(
        `/audit${query({ user_id: userId, entity_type: entity, date_from: from, date_to: to, page, page_size: 20 })}`,
      ),
    [userId, entity, from, to, page],
  )
  const filter = (set: (value: string) => void, value: string) => {
    set(value)
    setPage(1)
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">GOVERNANCE & ACCOUNTABILITY</div>
          <h1>Audit log</h1>
          <p>A record of who changed what, and when.</p>
        </div>
        <div className="inline-status">
          <ShieldCheck size={17} />
          Administrator access
        </div>
      </div>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>
              Activity history <span className="count-tag">{result.data?.total ?? '—'}</span>
            </h2>
            <p>Participant, sample, phenotype, and user account changes</p>
          </div>
        </div>
        <div className="filters">
          <select
            aria-label="Filter audit by user"
            value={userId}
            onChange={(event) => filter(setUserId, event.target.value)}
          >
            <option value="">All users</option>
            {users.data?.map((user) => (
              <option key={user.id} value={user.id}>
                {user.username}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter audit by entity"
            value={entity}
            onChange={(event) => filter(setEntity, event.target.value)}
          >
            <option value="">All record types</option>
            {['participant', 'sample', 'phenotype', 'user'].map((value) => (
              <option value={value} key={value}>
                {value === 'user' ? 'User account' : label(value)}
              </option>
            ))}
          </select>
          <div className="date-filter">
            <label htmlFor="audit-from">From (UTC)</label>
            <input
              id="audit-from"
              type="date"
              value={from}
              max={to || undefined}
              onChange={(event) => filter(setFrom, event.target.value)}
            />
          </div>
          <div className="date-filter">
            <label htmlFor="audit-to">To (UTC)</label>
            <input
              id="audit-to"
              type="date"
              min={from || undefined}
              value={to}
              onChange={(event) => filter(setTo, event.target.value)}
            />
          </div>
        </div>
        <Alert>{result.error || users.error}</Alert>
        {result.loading ? (
          <Loading />
        ) : !result.data?.items.length ? (
          <Empty title="No activity found">
            Changes to records appear here. Adjust filters to broaden your search.
          </Empty>
        ) : (
          <div className="audit-list">
            {result.data.items.map((event) => (
              <div className="audit-row" key={event.id}>
                <button
                  className="audit-main"
                  aria-expanded={expanded === event.id}
                  onClick={() => setExpanded(expanded === event.id ? undefined : event.id)}
                >
                  <div className={`activity-dot ${event.action.toLowerCase()}`}>
                    <span />
                  </div>
                  <div>
                    <strong>
                      {event.username ||
                        users.data?.find((user) => user.id === event.user_id)?.username ||
                        `User #${event.user_id}`}
                    </strong>
                    <span>
                      {label(event.action.toLowerCase())} · {label(event.entity_type)} #
                      {event.entity_id}
                    </span>
                  </div>
                  <time>{dateTime(event.occurred_at)}</time>
                  <ChevronDown size={16} className={expanded === event.id ? 'rotate' : ''} />
                </button>
                {expanded === event.id && (
                  <div className="audit-diff">
                    <table>
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Previous value</th>
                          <th>New value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(event.changed_fields).map(([field, values]) => (
                          <tr key={field}>
                            <td className="mono">{field}</td>
                            <td>
                              <code>{values.old == null ? '—' : JSON.stringify(values.old)}</code>
                            </td>
                            <td>
                              <code>{values.new == null ? '—' : JSON.stringify(values.new)}</code>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        <Pagination data={result.data} page={page} setPage={setPage} />
      </div>
    </>
  )
}

export function Accounts({
  currentUser,
  currentUserChanged,
}: {
  currentUser: User
  currentUserChanged: (user: User) => void
}) {
  const result = useLoad(() => api<User[]>('/auth/users'), [])
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<User>()
  const [statusTarget, setStatusTarget] = useState<User>()
  const [notice, setNotice] = useState('')
  const saved = (user: User, message: string) => {
    if (user.id === currentUser.id) currentUserChanged(user)
    setNotice(message)
    result.reload()
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ACCESS MANAGEMENT</div>
          <h1>Team accounts</h1>
          <p>Manage access for the research operations team.</p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setNotice('')
            setCreating(true)
          }}
        >
          <Plus size={17} />
          Create account
        </button>
      </div>
      <Alert success>{notice}</Alert>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>
              Portal users <span className="count-tag">{result.data?.length ?? '—'}</span>
            </h2>
            <p>Roles control each user’s available actions.</p>
          </div>
        </div>
        <Alert>{result.error}</Alert>
        {result.loading ? (
          <Loading />
        ) : !result.data?.length ? (
          <Empty title="No team accounts" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Account status</th>
                  <th aria-label="Account actions" />
                </tr>
              </thead>
              <tbody>
                {result.data.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className="user-cell">
                        <span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span>
                        <strong>{user.username}</strong>
                        {user.id === currentUser.id && <Badge>You</Badge>}
                      </div>
                    </td>
                    <td>{roleLabel[user.role]}</td>
                    <td>
                      <Badge tone={user.is_active ? 'green' : ''}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td>
                      <div className="row-actions account-actions">
                        <button
                          className="button secondary small"
                          aria-label={`Edit account ${user.username}`}
                          onClick={() => {
                            setNotice('')
                            setEditing(user)
                          }}
                        >
                          <Edit3 size={14} />
                          Edit
                        </button>
                        <button
                          className={`button secondary small ${user.is_active ? 'account-deactivate' : ''}`}
                          disabled={user.id === currentUser.id}
                          aria-label={`${user.is_active ? 'Deactivate' : 'Reactivate'} account ${user.username}`}
                          title={
                            user.id === currentUser.id
                              ? 'You cannot deactivate your own account.'
                              : undefined
                          }
                          onClick={() => {
                            setNotice('')
                            setStatusTarget(user)
                          }}
                        >
                          {user.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="account-help">
          Your own administrator role and active status are protected. Deactivation preserves the
          user’s records and history.
        </div>
      </div>
      {creating && (
        <AccountForm
          close={() => setCreating(false)}
          saved={(user) => saved(user, `Account ${user.username} created.`)}
        />
      )}
      {editing && (
        <AccountForm
          account={editing}
          isSelf={editing.id === currentUser.id}
          close={() => setEditing(undefined)}
          saved={(user) =>
            saved(
              user,
              user.role !== editing.role
                ? `Account ${user.username} updated. This user must sign in again to use their new role.`
                : `Account ${user.username} updated.`,
            )
          }
        />
      )}
      {statusTarget && (
        <AccountStatusDialog
          account={statusTarget}
          close={() => setStatusTarget(undefined)}
          saved={(user) =>
            saved(
              user,
              `Account ${user.username} ${user.is_active ? 'reactivated' : 'deactivated'}.`,
            )
          }
        />
      )}
    </>
  )
}

function AccountForm({
  account,
  isSelf = false,
  close,
  saved,
}: {
  account?: User
  isSelf?: boolean
  close: () => void
  saved: (user: User) => void
}) {
  const [form, setForm] = useState({
    username: account?.username || '',
    password: '',
    role: account?.role || ('field_officer' as Role),
  })
  const [error, setError] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const unchanged = account && form.username === account.username && form.role === account.role
  const dismiss = () => {
    if (!busy) close()
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setErrors({})
    try {
      const payload = account
        ? {
            ...(form.username !== account.username ? { username: form.username } : {}),
            ...(form.role !== account.role ? { role: form.role } : {}),
          }
        : form
      const user = await api<User>(account ? `/auth/users/${account.id}` : '/auth/register', {
        method: account ? 'PATCH' : 'POST',
        body: body(payload),
      })
      saved(user)
      close()
    } catch (reason) {
      setError((reason as Error).message)
      setErrors(fieldErrors(reason))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      title={account ? 'Edit team account' : 'Create team account'}
      subtitle={
        account
          ? `Update ${account.username}’s username or role.`
          : 'Assign the role required for this team member’s work.'
      }
      close={dismiss}
    >
      <form onSubmit={submit}>
        <Alert>{error}</Alert>
        <Field
          label="Username"
          error={errors.username}
          hint="Letters, numbers, underscores, periods and hyphens."
        >
          <input
            aria-label={account ? 'Username' : 'New username'}
            required
            minLength={3}
            maxLength={80}
            pattern={'[a-zA-Z0-9_.\\-]+'}
            disabled={busy}
            autoComplete="off"
            value={form.username}
            onChange={(event) =>
              setForm((previous) => ({ ...previous, username: event.target.value }))
            }
          />
        </Field>
        {!account && (
          <Field label="Password" error={errors.password} hint="At least 12 characters">
            <input
              aria-label="New password"
              required
              minLength={12}
              maxLength={256}
              disabled={busy}
              autoComplete="new-password"
              type="password"
              value={form.password}
              onChange={(event) =>
                setForm((previous) => ({ ...previous, password: event.target.value }))
              }
            />
          </Field>
        )}
        <Field
          label="Role"
          error={errors.role}
          hint={
            isSelf
              ? 'You cannot change your own administrator role.'
              : account
                ? 'A role change requires this user to sign in again.'
                : undefined
          }
        >
          <select
            aria-label={account ? 'Account role' : 'New account role'}
            value={form.role}
            disabled={busy || isSelf}
            onChange={(event) =>
              setForm((previous) => ({ ...previous, role: event.target.value as Role }))
            }
          >
            {Object.entries(roleLabel).map(([role, title]) => (
              <option key={role} value={role}>
                {title}
              </option>
            ))}
          </select>
        </Field>
        <footer>
          <button className="button secondary" type="button" disabled={busy} onClick={dismiss}>
            Cancel
          </button>
          <button className="button primary" disabled={busy || Boolean(unchanged)}>
            {busy ? 'Saving…' : account ? 'Save changes' : 'Create account'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function AccountStatusDialog({
  account,
  close,
  saved,
}: {
  account: User
  close: () => void
  saved: (user: User) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const action = account.is_active ? 'Deactivate' : 'Reactivate'
  const dismiss = () => {
    if (!busy) close()
  }
  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      const user = await api<User>(`/auth/users/${account.id}`, {
        method: 'PATCH',
        body: body({ is_active: !account.is_active }),
      })
      saved(user)
      close()
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title={`${action} ${account.username}?`} close={dismiss}>
      <p className="modal-copy">
        {account.is_active
          ? 'This user will lose access to the portal. Their existing sessions will be rejected on the next request. Their records and audit history will be preserved.'
          : `This user will be able to sign in again as ${roleLabel[account.role].toLowerCase()}.`}
      </p>
      <Alert>{error}</Alert>
      <footer>
        <button className="button secondary" disabled={busy} onClick={dismiss}>
          Cancel
        </button>
        <button
          className={`button ${account.is_active ? 'danger' : 'primary'}`}
          disabled={busy}
          onClick={() => void submit()}
        >
          {busy ? 'Saving…' : `${action} account`}
        </button>
      </footer>
    </Modal>
  )
}
