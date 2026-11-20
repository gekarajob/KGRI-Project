import { useState, type FormEvent } from 'react'
import { ArrowRight, ArrowUpRight, FlaskConical, Plus, Search, Trash2 } from 'lucide-react'
import { api, body, query } from './api'
import {
  Alert,
  Badge,
  ConfirmDelete,
  Empty,
  Field,
  fieldErrors,
  Loading,
  Modal,
  Pagination,
  useLoad,
} from './ui'
import { date, label, platforms, states, type Page, type Role, type Sample } from './types'
import { ParticipantSelect } from './Participants'

function SampleForm({
  sample,
  close,
  saved,
}: {
  sample?: Sample
  close: () => void
  saved: () => void
}) {
  const [form, setForm] = useState({
    participant_id: sample?.participant_id.toString() || '',
    sample_type: sample?.sample_type || 'blood',
    platform: sample?.platform || '',
    batch_id: sample?.batch_id || '',
    sequencing_file_path: sample?.sequencing_file_path || '',
    mean_coverage: sample?.mean_coverage?.toString() || '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const update = (key: keyof typeof form, value: string) =>
    setForm((previous) => ({
      ...previous,
      [key]: value,
      ...(key === 'platform' && value === 'olink'
        ? { sequencing_file_path: '', mean_coverage: '' }
        : {}),
    }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setErrors({})
    const metadata = {
      sample_type: form.sample_type,
      platform: form.platform || null,
      batch_id: form.batch_id || null,
      sequencing_file_path: form.sequencing_file_path || null,
      mean_coverage: form.mean_coverage === '' ? null : Number(form.mean_coverage),
    }
    try {
      await api(`/samples${sample ? `/${sample.id}` : ''}`, {
        method: sample ? 'PATCH' : 'POST',
        body: body({
          ...metadata,
          ...(!sample ? { participant_id: Number(form.participant_id) } : {}),
        }),
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
      title={sample ? 'Edit sample metadata' : 'Register sample'}
      subtitle={
        sample
          ? `SMP-${String(sample.id).padStart(4, '0')}`
          : 'New samples begin in the collected state.'
      }
      close={close}
    >
      <form onSubmit={submit}>
        <Alert>{error}</Alert>
        {!sample && (
          <Field label="Participant" error={errors.participant_id}>
            <ParticipantSelect
              value={form.participant_id}
              onChange={(value) => update('participant_id', value)}
            />
          </Field>
        )}
        <div className="form-grid">
          <Field label="Sample type" error={errors.sample_type}>
            <select
              aria-label="Sample type"
              value={form.sample_type}
              onChange={(event) => update('sample_type', event.target.value)}
            >
              {['blood', 'dna', 'saliva'].map((value) => (
                <option value={value} key={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Platform" error={errors.platform}>
            <select
              aria-label="Platform"
              value={form.platform}
              onChange={(event) => update('platform', event.target.value)}
            >
              <option value="">Not assigned</option>
              {platforms.map((value) => (
                <option value={value} key={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Batch ID" error={errors.batch_id}>
            <input
              aria-label="Batch ID"
              maxLength={100}
              value={form.batch_id}
              onChange={(event) => update('batch_id', event.target.value)}
            />
          </Field>
          <Field
            label="Mean coverage"
            error={errors.mean_coverage}
            hint={
              form.platform === 'olink'
                ? 'Olink records have no coverage value.'
                : 'Nonnegative sequencing depth'
            }
          >
            <input
              aria-label="Mean coverage"
              type="number"
              min={0}
              step="any"
              disabled={form.platform === 'olink'}
              value={form.mean_coverage}
              onChange={(event) => update('mean_coverage', event.target.value)}
            />
          </Field>
        </div>
        <Field
          label="Sequencing file path"
          error={errors.sequencing_file_path}
          hint={
            form.platform === 'olink'
              ? 'Olink records have no sequencing file.'
              : 'Use a .cram or .bam file path.'
          }
        >
          <input
            aria-label="Sequencing file path"
            maxLength={1000}
            disabled={form.platform === 'olink'}
            placeholder="/data/sequencing/sample.cram"
            value={form.sequencing_file_path}
            onChange={(event) => update('sequencing_file_path', event.target.value)}
          />
        </Field>
        <footer>
          <button className="button secondary" type="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? 'Saving…' : sample ? 'Save metadata' : 'Register sample'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

function SampleDetail({
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
  const result = useLoad(() => api<Sample>(`/samples/${id}`), [id])
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const sample = result.data
  const next =
    sample?.allowed_next_states ||
    (sample && states.indexOf(sample.status) < states.length - 1
      ? [states[states.indexOf(sample.status) + 1]]
      : [])
  const transition = async (status: string) => {
    setBusy(true)
    setError('')
    try {
      await api(`/samples/${id}/status`, { method: 'PATCH', body: body({ status }) })
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
      title={`Sample SMP-${String(id).padStart(4, '0')}`}
      subtitle={
        sample
          ? `${sample.kgri_id || `Participant #${sample.participant_id}`} · ${sample.participant_name || ''}`
          : undefined
      }
      close={close}
      wide
    >
      <Alert>{result.error || error}</Alert>
      {result.loading ? (
        <Loading />
      ) : (
        sample && (
          <>
            <div className="detail-summary">
              <div className="person-icon">
                <FlaskConical size={24} />
              </div>
              <div>
                <strong>{label(sample.sample_type)} sample</strong>
                <span>Registered {date(sample.created_at)}</span>
              </div>
              <Badge tone={sample.status === 'qc_passed' ? 'green' : ''}>
                {label(sample.status)}
              </Badge>
            </div>
            <section className="detail-section">
              <h3>Sample journey</h3>
              <div className="status-journey">
                {states.map((status, index) => (
                  <div
                    key={status}
                    className={index <= states.indexOf(sample.status) ? 'complete' : ''}
                  >
                    <span>{index < states.indexOf(sample.status) ? '✓' : index + 1}</span>
                    <small>{label(status)}</small>
                  </div>
                ))}
              </div>
              {role !== 'field_officer' && next.length > 0 && (
                <div className="next-status">
                  <span>Next step</span>
                  {next.map((status) => (
                    <button
                      className="button primary small"
                      disabled={busy}
                      key={status}
                      onClick={() => void transition(status)}
                    >
                      {busy ? 'Updating…' : `Mark ${label(status).toLowerCase()}`}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
              )}
              {sample.status === 'library_prepped' && role !== 'field_officer' && (
                <p className="form-hint">
                  Set the platform, batch ID, and sequencing metadata before marking the sample
                  sequenced.
                </p>
              )}
            </section>
            <section className="detail-section">
              <div className="section-row">
                <h3>Sequencing metadata</h3>
                {role !== 'field_officer' && (
                  <button className="text-button" onClick={() => setEditing(true)}>
                    Edit metadata
                    <ArrowUpRight size={15} />
                  </button>
                )}
              </div>
              <div className="detail-facts">
                <div>
                  <small>Platform</small>
                  <strong>{sample.platform ? label(sample.platform) : 'Not assigned'}</strong>
                </div>
                <div>
                  <small>Batch</small>
                  <strong>{sample.batch_id || 'Not assigned'}</strong>
                </div>
                <div>
                  <small>Mean coverage</small>
                  <strong>
                    {sample.mean_coverage !== null ? `${sample.mean_coverage}×` : 'Not recorded'}
                  </strong>
                </div>
              </div>
              <div className="path-field">
                <small>Sequencing file</small>
                <code>{sample.sequencing_file_path || 'Not recorded'}</code>
              </div>
            </section>
          </>
        )
      )}
      {editing && sample && (
        <SampleForm
          sample={sample}
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

export default function Samples({ role }: { role: Role }) {
  const [status, setStatus] = useState('')
  const [platform, setPlatform] = useState('')
  const [site, setSite] = useState('')
  const [page, setPage] = useState(1)
  const [register, setRegister] = useState(false)
  const [selected, setSelected] = useState<number>()
  const [archive, setArchive] = useState<Sample>()
  const result = useLoad(
    () => api<Page<Sample>>(`/samples${query({ status, platform, site, page, page_size: 20 })}`),
    [status, platform, site, page],
  )
  const filter = (set: (value: string) => void, value: string) => {
    set(value)
    setPage(1)
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">LABORATORY OPERATIONS</div>
          <h1>Samples & sequencing</h1>
          <p>Track every sample from collection to quality control.</p>
        </div>
        {role !== 'field_officer' && (
          <button className="button primary" onClick={() => setRegister(true)}>
            <Plus size={17} />
            Register sample
          </button>
        )}
      </div>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>
              Sample register <span className="count-tag">{result.data?.total ?? '—'}</span>
            </h2>
            <p>Physical samples and their sequencing records</p>
          </div>
        </div>
        <div className="filters">
          <div className="search-input">
            <Search size={17} />
            <input
              aria-label="Filter samples by site"
              placeholder="Filter by recruitment site…"
              value={site}
              onChange={(event) => filter(setSite, event.target.value)}
            />
          </div>
          <select
            aria-label="Filter samples by status"
            value={status}
            onChange={(event) => filter(setStatus, event.target.value)}
          >
            <option value="">All statuses</option>
            {states.map((value) => (
              <option value={value} key={value}>
                {label(value)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter samples by platform"
            value={platform}
            onChange={(event) => filter(setPlatform, event.target.value)}
          >
            <option value="">All platforms</option>
            {platforms.map((value) => (
              <option value={value} key={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </div>
        <Alert>{result.error}</Alert>
        {result.loading ? (
          <Loading />
        ) : !result.data?.items.length ? (
          <Empty title="No samples found">Register a sample or adjust the filters.</Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Sample</th>
                  <th>Participant</th>
                  <th>Current status</th>
                  <th>Platform / Batch</th>
                  <th>Site</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {result.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button className="table-link" onClick={() => setSelected(item.id)}>
                        <strong className="mono">SMP-{String(item.id).padStart(4, '0')}</strong>
                        <span>{label(item.sample_type)}</span>
                      </button>
                    </td>
                    <td>
                      {item.participant_name || `Participant #${item.participant_id}`}
                      <span className="cell-sub mono">{item.kgri_id || '—'}</span>
                    </td>
                    <td>
                      <Badge tone={item.status === 'qc_passed' ? 'green' : ''}>
                        {label(item.status)}
                      </Badge>
                    </td>
                    <td>
                      {item.platform ? label(item.platform) : 'Not assigned'}
                      <span className="cell-sub">{item.batch_id || '—'}</span>
                    </td>
                    <td className="muted">{item.recruitment_site || '—'}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`View sample ${item.id}`}
                          onClick={() => setSelected(item.id)}
                        >
                          <ArrowUpRight size={18} />
                        </button>
                        {role !== 'field_officer' && (
                          <button
                            className="icon-button archive-button"
                            aria-label={`Archive sample ${item.id}`}
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
      {register && <SampleForm close={() => setRegister(false)} saved={result.reload} />}
      {selected !== undefined && (
        <SampleDetail
          id={selected}
          role={role}
          close={() => setSelected(undefined)}
          changed={result.reload}
        />
      )}
      {archive && (
        <ConfirmDelete
          label={`sample SMP-${String(archive.id).padStart(4, '0')}`}
          close={() => setArchive(undefined)}
          submit={async () => {
            await api(`/samples/${archive.id}`, { method: 'DELETE' })
            result.reload()
          }}
        />
      )}
    </>
  )
}
