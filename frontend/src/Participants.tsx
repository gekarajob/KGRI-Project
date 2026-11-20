import { useState, type ComponentProps, type FormEvent } from 'react'
import { ArrowUpRight, Edit3, Plus, Search, Trash2, UserRound, X } from 'lucide-react'
import { api, body, query } from './api'
import {
  Alert,
  Badge,
  ConfirmDelete,
  ConsentDot,
  Empty,
  Field,
  fieldErrors,
  Loading,
  Modal,
  Pagination,
  useLoad,
} from './ui'
import { date, label, type Consent, type Page, type Participant, type Role } from './types'

const consentLabels = {
  broad_consent: 'Broad research',
  recontact_consent: 'Recontact',
  data_sharing_consent: 'Data sharing',
}
const emptyConsent: Consent = {
  broad_consent: false,
  recontact_consent: false,
  data_sharing_consent: false,
}

export function ParticipantSelect({
  value,
  onChange,
  disabled = false,
  id,
  'aria-describedby': describedBy,
  'aria-invalid': invalid,
}: {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
} & Pick<ComponentProps<'select'>, 'id' | 'aria-describedby' | 'aria-invalid'>) {
  const [search, setSearch] = useState('')
  const result = useLoad(
    () => api<Page<Participant>>(`/participants${query({ search, page_size: 100 })}`),
    [search],
  )
  return (
    <div className="participant-select">
      <input
        aria-label="Search participant options"
        placeholder="Find a participant by name or KGRI ID"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        disabled={disabled}
      />
      <select
        id={id}
        aria-label="Participant"
        aria-describedby={describedBy}
        aria-invalid={invalid}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        required
      >
        <option value="">Select participant</option>
        {value && !result.data?.items.some((item) => String(item.id) === value) && (
          <option value={value}>Participant #{value}</option>
        )}
        {result.data?.items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.kgri_id} · {item.full_name}
          </option>
        ))}
      </select>
      {result.error && <small className="field-error">{result.error}</small>}
    </div>
  )
}

export function ParticipantForm({
  participant,
  close,
  saved,
}: {
  participant?: Participant
  close: () => void
  saved: () => void
}) {
  const [form, setForm] = useState({
    full_name: participant?.full_name || '',
    age: participant?.age.toString() || '',
    sex: participant?.sex || '',
    community: participant?.community || '',
    county: participant?.county || '',
    recruitment_site: participant?.recruitment_site || '',
  })
  const [consent, setConsent] = useState<Consent>(participant?.consent || emptyConsent)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (key: keyof typeof form, value: string) =>
    setForm((previous) => ({ ...previous, [key]: value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setErrors({})
    try {
      const payload = {
        ...form,
        age: Number(form.age),
        ...(!participant
          ? {
              consent: {
                broad_consent: consent.broad_consent,
                recontact_consent: consent.recontact_consent,
                data_sharing_consent: consent.data_sharing_consent,
              },
            }
          : {}),
      }
      await api(`/participants${participant ? `/${participant.id}` : ''}`, {
        method: participant ? 'PATCH' : 'POST',
        body: body(payload),
      })
      saved()
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
      title={participant ? 'Edit participant' : 'Register participant'}
      subtitle={participant?.kgri_id || 'Create a participant record and capture consent.'}
      close={close}
    >
      <form onSubmit={submit}>
        <Alert>{error}</Alert>
        <div className="form-grid">
          <Field label="Full name" error={errors.full_name}>
            <input
              aria-label="Full name"
              autoComplete="off"
              required
              maxLength={200}
              value={form.full_name}
              onChange={(event) => update('full_name', event.target.value)}
            />
          </Field>
          <Field label="Age at enrolment" error={errors.age} hint="0–120 years">
            <input
              aria-label="Age at enrolment"
              type="number"
              required
              min={0}
              max={120}
              value={form.age}
              onChange={(event) => update('age', event.target.value)}
            />
          </Field>
          <Field label="Sex" error={errors.sex}>
            <select
              aria-label="Sex"
              required
              value={form.sex}
              onChange={(event) => update('sex', event.target.value)}
            >
              <option value="">Select sex</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </Field>
          <Field label="Community" error={errors.community}>
            <input
              aria-label="Community"
              required
              maxLength={100}
              value={form.community}
              onChange={(event) => update('community', event.target.value)}
            />
          </Field>
          <Field label="County" error={errors.county}>
            <input
              aria-label="County"
              required
              maxLength={100}
              value={form.county}
              onChange={(event) => update('county', event.target.value)}
            />
          </Field>
          <Field label="Recruitment site" error={errors.recruitment_site}>
            <input
              aria-label="Recruitment site"
              required
              maxLength={100}
              value={form.recruitment_site}
              onChange={(event) => update('recruitment_site', event.target.value)}
            />
          </Field>
        </div>
        {!participant && (
          <div className="consent-form">
            <h3>Participant consent</h3>
            <p>Record each choice independently.</p>
            {Object.entries(consentLabels).map(([key, title]) => (
              <label className="check-row" key={key}>
                <input
                  type="checkbox"
                  checked={consent[key as keyof typeof consentLabels]}
                  onChange={(event) =>
                    setConsent((previous) => ({ ...previous, [key]: event.target.checked }))
                  }
                />
                <span>{title}</span>
              </label>
            ))}
          </div>
        )}
        <footer>
          <button className="button secondary" type="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? 'Saving…' : participant ? 'Save changes' : 'Register participant'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function ParticipantDetail({
  id,
  role,
  close,
  changed,
}: {
  id: number
  role: Role
  close: () => void
  changed: () => void
}) {
  const result = useLoad(() => api<Participant>(`/participants/${id}`), [id])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const participant = result.data
  const changeConsent = async (key: keyof typeof consentLabels, value: boolean) => {
    setBusy(true)
    setError('')
    try {
      await api(`/participants/${id}/consent`, { method: 'PATCH', body: body({ [key]: value }) })
      result.reload()
      changed()
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      title={participant?.full_name || 'Participant details'}
      subtitle={participant?.kgri_id}
      close={close}
      wide
    >
      <Alert>{result.error || error}</Alert>
      {result.loading ? (
        <Loading />
      ) : (
        participant && (
          <>
            <div className="detail-summary">
              <div className="person-icon">
                <UserRound size={25} />
              </div>
              <div>
                <strong>{participant.kgri_id}</strong>
                <span>
                  {participant.age} years · {label(participant.sex)} · {participant.community}
                </span>
              </div>
              {role !== 'lab_tech' && (
                <button className="button secondary small" onClick={() => setEditing(true)}>
                  <Edit3 size={15} />
                  Edit details
                </button>
              )}
            </div>
            <div className="detail-facts">
              <div>
                <small>County</small>
                <strong>{participant.county}</strong>
              </div>
              <div>
                <small>Recruitment site</small>
                <strong>{participant.recruitment_site}</strong>
              </div>
              <div>
                <small>Registered</small>
                <strong>{date(participant.created_at)}</strong>
              </div>
            </div>
            <section className="detail-section">
              <h3>Consent record</h3>
              {Object.entries(consentLabels).map(([key, title]) => (
                <div className="consent-record" key={key}>
                  <div>
                    <strong>{title}</strong>
                    <small>
                      {date(
                        participant.consent[`${key}_recorded_at` as keyof Consent] as string | null,
                      )}
                    </small>
                  </div>
                  <label className="switch">
                    <input
                      aria-label={`${title} consent`}
                      type="checkbox"
                      disabled={role === 'lab_tech' || busy}
                      checked={participant.consent[key as keyof typeof consentLabels]}
                      onChange={(event) =>
                        void changeConsent(key as keyof typeof consentLabels, event.target.checked)
                      }
                    />
                    <span />
                  </label>
                </div>
              ))}
            </section>
            <section className="detail-section">
              <h3>
                Linked samples <span className="count-tag">{participant.samples?.length || 0}</span>
              </h3>
              {participant.samples?.length ? (
                <div className="mini-list">
                  {participant.samples.map((sample) => (
                    <div key={sample.id}>
                      <strong>
                        SMP-{String(sample.id).padStart(4, '0')}
                        <small>{label(sample.sample_type)}</small>
                      </strong>
                      <Badge>{label(sample.status)}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No samples registered.</p>
              )}
            </section>
            <section className="detail-section">
              <h3>
                Phenotype captures{' '}
                <span className="count-tag">{participant.phenotypes?.length || 0}</span>
              </h3>
              {participant.phenotypes_restricted ? (
                <p className="muted">
                  Phenotype records are available to field officers and administrators.
                </p>
              ) : participant.phenotypes?.length ? (
                <div className="mini-list">
                  {participant.phenotypes.map((record) => (
                    <div key={record.id}>
                      <strong>
                        {date(record.captured_at)}
                        <small>
                          {record.height_cm} cm · {record.weight_kg} kg
                        </small>
                      </strong>
                      <span>
                        {record.systolic_bp}/{record.diastolic_bp} mmHg
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No phenotype records captured.</p>
              )}
            </section>
          </>
        )
      )}
      {editing && participant && (
        <ParticipantForm
          participant={participant}
          close={() => setEditing(false)}
          saved={() => {
            result.reload()
            changed()
          }}
        />
      )}
    </Modal>
  )
}

export default function Participants({ role }: { role: Role }) {
  const [search, setSearch] = useState('')
  const [site, setSite] = useState('')
  const [county, setCounty] = useState('')
  const [consentFilter, setConsentFilter] = useState('')
  const [page, setPage] = useState(1)
  const [register, setRegister] = useState(false)
  const [selected, setSelected] = useState<number>()
  const [archive, setArchive] = useState<Participant>()
  const [consentBusy, setConsentBusy] = useState<number>()
  const [mutationError, setMutationError] = useState('')
  const result = useLoad(
    () =>
      api<Page<Participant>>(
        `/participants${query({ search, site, county, page, page_size: 20, ...(consentFilter ? { [consentFilter]: true } : {}) })}`,
      ),
    [search, site, county, page, consentFilter],
  )
  const changeConsent = async (participant: Participant, key: keyof typeof consentLabels) => {
    setConsentBusy(participant.id)
    setMutationError('')
    try {
      await api(`/participants/${participant.id}/consent`, {
        method: 'PATCH',
        body: body({ [key]: !participant.consent[key] }),
      })
      result.reload()
    } catch (reason) {
      setMutationError((reason as Error).message)
    } finally {
      setConsentBusy(undefined)
    }
  }
  const reset = () => {
    setSearch('')
    setSite('')
    setCounty('')
    setConsentFilter('')
    setPage(1)
  }
  const filter = (set: (value: string) => void, value: string) => {
    set(value)
    setPage(1)
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PARTICIPANT MANAGEMENT</div>
          <h1>Participant registry</h1>
          <p>Manage registrations and each participant’s consent.</p>
        </div>
        {role !== 'lab_tech' && (
          <button className="button primary" onClick={() => setRegister(true)}>
            <Plus size={17} />
            Register participant
          </button>
        )}
      </div>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>
              All participants <span className="count-tag">{result.data?.total ?? '—'}</span>
            </h2>
            <p>Active records in the KGRI registry</p>
          </div>
        </div>
        <div className="filters">
          <div className="search-input">
            <Search size={17} />
            <input
              aria-label="Search participants"
              placeholder="Search name, KGRI ID, county or site…"
              value={search}
              onChange={(event) => filter(setSearch, event.target.value)}
            />
          </div>
          <input
            aria-label="Filter by county"
            placeholder="County"
            value={county}
            onChange={(event) => filter(setCounty, event.target.value)}
          />
          <input
            aria-label="Filter by recruitment site"
            placeholder="Recruitment site"
            value={site}
            onChange={(event) => filter(setSite, event.target.value)}
          />
          <select
            aria-label="Filter by consent"
            value={consentFilter}
            onChange={(event) => filter(setConsentFilter, event.target.value)}
          >
            <option value="">All consent</option>
            {Object.entries(consentLabels).map(([key, title]) => (
              <option value={key} key={key}>
                {title} granted
              </option>
            ))}
          </select>
          {(search || site || county || consentFilter) && (
            <button
              className="icon-button"
              title="Clear filters"
              aria-label="Clear filters"
              onClick={reset}
            >
              <X size={17} />
            </button>
          )}
        </div>
        <Alert>{result.error || mutationError}</Alert>
        {result.loading ? (
          <Loading />
        ) : !result.data?.items.length ? (
          <Empty title="No participants found">Register a participant or adjust the filters.</Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Participant</th>
                  <th>Demographics</th>
                  <th>County / Site</th>
                  <th>
                    <span title="Broad research / Recontact / Data sharing">
                      Consent <span className="th-hint">B · R · D</span>
                    </span>
                  </th>
                  <th>Registered</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {result.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button className="table-link" onClick={() => setSelected(item.id)}>
                        <strong>{item.full_name}</strong>
                        <span className="mono">{item.kgri_id}</span>
                      </button>
                    </td>
                    <td>
                      {item.age} years<span className="cell-sub">{label(item.sex)}</span>
                    </td>
                    <td>
                      {item.county}
                      <span className="cell-sub">{item.recruitment_site}</span>
                    </td>
                    <td>
                      <div className="consent-dots">
                        {Object.entries(consentLabels).map(([key, title]) =>
                          role === 'lab_tech' ? (
                            <ConsentDot
                              key={key}
                              value={item.consent[key as keyof typeof consentLabels]}
                            />
                          ) : (
                            <button
                              className="consent-toggle"
                              key={key}
                              aria-label={`${item.consent[key as keyof typeof consentLabels] ? 'Withdraw' : 'Grant'} ${title.toLowerCase()} consent for ${item.full_name}`}
                              disabled={consentBusy === item.id}
                              onClick={() =>
                                void changeConsent(item, key as keyof typeof consentLabels)
                              }
                            >
                              <ConsentDot value={item.consent[key as keyof typeof consentLabels]} />
                            </button>
                          ),
                        )}
                      </div>
                    </td>
                    <td className="muted">{date(item.created_at)}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`View ${item.full_name}`}
                          onClick={() => setSelected(item.id)}
                        >
                          <ArrowUpRight size={18} />
                        </button>
                        {role === 'admin' && (
                          <button
                            className="icon-button archive-button"
                            aria-label={`Archive ${item.full_name}`}
                            onClick={() => setArchive(item)}
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination data={result.data} page={page} setPage={setPage} />
      </div>
      {register && <ParticipantForm close={() => setRegister(false)} saved={result.reload} />}
      {selected !== undefined && (
        <ParticipantDetail
          id={selected}
          role={role}
          close={() => setSelected(undefined)}
          changed={result.reload}
        />
      )}
      {archive && (
        <ConfirmDelete
          label={archive.full_name}
          close={() => setArchive(undefined)}
          submit={async () => {
            await api(`/participants/${archive.id}`, { method: 'DELETE' })
            result.reload()
          }}
        />
      )}
    </>
  )
}
