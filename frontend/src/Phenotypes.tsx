import { useState, type FormEvent } from 'react'
import { Download, Edit3, Plus, Search, Trash2 } from 'lucide-react'
import { api, body, downloadCsv, query } from './api'
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
import { dateTime, type Page, type Phenotype, type Role, type Study } from './types'
import { ParticipantSelect } from './Participants'

const localDateTime = (value: string) => {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const measurementFields = [
  { key: 'height_cm', title: 'Height (cm)', min: 50, max: 250 },
  { key: 'weight_kg', title: 'Weight (kg)', min: 10, max: 300 },
  { key: 'systolic_bp', title: 'Systolic BP (mmHg)', min: 60, max: 250 },
  { key: 'diastolic_bp', title: 'Diastolic BP (mmHg)', min: 30, max: 150 },
] as const

function PhenotypeForm({
  record,
  studies,
  close,
  saved,
}: {
  record?: Phenotype
  studies: Study[]
  close: () => void
  saved: () => void
}) {
  const [form, setForm] = useState({
    participant_id: record?.participant_id.toString() || '',
    study_id: record?.study_id.toString() || studies[0]?.id.toString() || '',
    captured_at: localDateTime(record?.captured_at || new Date().toISOString()),
    height_cm: record?.height_cm.toString() || '',
    weight_kg: record?.weight_kg.toString() || '',
    systolic_bp: record?.systolic_bp.toString() || '',
    diastolic_bp: record?.diastolic_bp.toString() || '',
    malaria_history: record?.malaria_history || false,
    livestock_contact: record?.livestock_contact || false,
    notes: record?.notes || '',
  })
  const [error, setError] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const update = (key: keyof typeof form, value: string | boolean) =>
    setForm((previous) => ({ ...previous, [key]: value }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setErrors({})
    if (Number(form.systolic_bp) <= Number(form.diastolic_bp)) {
      setErrors({ systolic_bp: 'Systolic blood pressure must be greater than diastolic.' })
      return
    }
    setBusy(true)
    const payload = {
      ...form,
      participant_id: Number(form.participant_id),
      study_id: Number(form.study_id),
      captured_at: new Date(form.captured_at).toISOString(),
      height_cm: Number(form.height_cm),
      weight_kg: Number(form.weight_kg),
      systolic_bp: Number(form.systolic_bp),
      diastolic_bp: Number(form.diastolic_bp),
      notes: form.notes || null,
    }
    if (record) {
      delete (payload as Partial<typeof payload>).participant_id
    }
    try {
      await api(`/phenotypes${record ? `/${record.id}` : ''}`, {
        method: record ? 'PATCH' : 'POST',
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
      title={record ? 'Edit phenotype record' : 'Capture phenotype'}
      subtitle={
        record
          ? `${record.kgri_id || `Participant #${record.participant_id}`} · ${record.participant_name || ''}`
          : 'Record observations for a participant and study.'
      }
      close={close}
    >
      <form onSubmit={submit}>
        <Alert>{error}</Alert>
        {!record && (
          <Field label="Participant" error={errors.participant_id}>
            <ParticipantSelect
              value={form.participant_id}
              onChange={(value) => update('participant_id', value)}
            />
          </Field>
        )}
        <div className="form-grid">
          <Field label="Study" error={errors.study_id}>
            <select
              aria-label="Study"
              required
              value={form.study_id}
              onChange={(event) => update('study_id', event.target.value)}
            >
              <option value="">Select study</option>
              {studies.map((study) => (
                <option key={study.id} value={study.id}>
                  {study.code}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Capture date and time" error={errors.captured_at}>
            <input
              aria-label="Capture date and time"
              type="datetime-local"
              required
              value={form.captured_at}
              onChange={(event) => update('captured_at', event.target.value)}
            />
          </Field>
          {measurementFields.map((field) => (
            <Field
              key={field.key}
              label={field.title}
              error={errors[field.key]}
              hint={`${field.min}–${field.max}`}
            >
              <input
                aria-label={field.title}
                type="number"
                step="any"
                required
                min={field.min}
                max={field.max}
                value={form[field.key]}
                onChange={(event) => update(field.key, event.target.value)}
              />
            </Field>
          ))}
        </div>
        <div className="checkbox-group">
          <label className="check-row">
            <input
              type="checkbox"
              checked={form.malaria_history}
              onChange={(event) => update('malaria_history', event.target.checked)}
            />
            <span>History of malaria</span>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={form.livestock_contact}
              onChange={(event) => update('livestock_contact', event.target.checked)}
            />
            <span>Contact with livestock</span>
          </label>
        </div>
        <Field label="Notes" error={errors.notes} hint={`${form.notes.length}/500 characters`}>
          <textarea
            aria-label="Notes"
            maxLength={500}
            rows={3}
            value={form.notes}
            onChange={(event) => update('notes', event.target.value)}
          />
        </Field>
        <footer>
          <button className="button secondary" type="button" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save phenotype record'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

export default function Phenotypes({ role }: { role: Role }) {
  const [study, setStudy] = useState('')
  const [site, setSite] = useState('')
  const [page, setPage] = useState(1)
  const [entry, setEntry] = useState(false)
  const [editing, setEditing] = useState<Phenotype>()
  const [archive, setArchive] = useState<Phenotype>()
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState(false)
  const studies = useLoad(() => api<Study[]>('/studies'), [])
  const selectedStudy = study || studies.data?.[0]?.id.toString() || ''
  const result = useLoad(
    () =>
      api<Page<Phenotype>>(`/phenotypes${query({ study_id: selectedStudy, site, page, page_size: 20 })}`),
    [selectedStudy, site, page],
  )
  const download = async () => {
    setExporting(true)
    setExportError('')
    try {
      await downloadCsv(
        `/phenotypes/export${query({ study_id: selectedStudy, site })}`,
      )
    } catch (reason) {
      setExportError((reason as Error).message)
    } finally {
      setExporting(false)
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">HEALTH OBSERVATIONS</div>
          <h1>Phenotype records</h1>
          <p>Capture measurements and export study observations.</p>
        </div>
        <div className="heading-actions">
          <button
            className="button secondary"
            disabled={exporting || !studies.data?.length}
            onClick={() => void download()}
          >
            <Download size={17} />
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
          <button
            className="button primary"
            disabled={!studies.data?.length}
            onClick={() => setEntry(true)}
          >
            <Plus size={17} />
            Capture phenotype
          </button>
        </div>
      </div>
      <Alert>{exportError || studies.error}</Alert>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>
              Study observations <span className="count-tag">{result.data?.total ?? '—'}</span>
            </h2>
            <p>Participant measurements and exposure histories</p>
          </div>
          <Badge>Validated measurements</Badge>
        </div>
        <div className="filters">
          <div className="search-input">
            <Search size={17} />
            <input
              aria-label="Filter phenotypes by site"
              placeholder="Filter by recruitment site…"
              value={site}
              onChange={(event) => {
                setSite(event.target.value)
                setPage(1)
              }}
            />
          </div>
          <select
            aria-label="Filter phenotypes by study"
            value={selectedStudy}
            onChange={(event) => {
              setStudy(event.target.value)
              setPage(1)
            }}
          >
            <option value="" disabled>Select study</option>
            {studies.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code}
              </option>
            ))}
          </select>
        </div>
        <Alert>{result.error}</Alert>
        {result.loading ? (
          <Loading />
        ) : !result.data?.items.length ? (
          <Empty title="No phenotype records found">
            Capture a phenotype or adjust the filters.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Participant / Study</th>
                  <th>Height / Weight</th>
                  <th>Blood pressure</th>
                  <th>History / Exposure</th>
                  <th>Captured</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {result.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>
                        {item.participant_name || `Participant #${item.participant_id}`}
                      </strong>
                      <span className="cell-sub mono">
                        {item.kgri_id} · {item.study_code}
                      </span>
                    </td>
                    <td>
                      {item.height_cm} cm<span className="cell-sub">{item.weight_kg} kg</span>
                    </td>
                    <td>
                      <strong>
                        {item.systolic_bp}/{item.diastolic_bp}
                      </strong>
                      <span className="cell-sub">mmHg</span>
                    </td>
                    <td>
                      <span className="small-text">
                        Malaria {item.malaria_history ? 'Yes' : 'No'}
                      </span>
                      <span className="cell-sub">
                        Livestock {item.livestock_contact ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td className="muted">{dateTime(item.captured_at)}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`Edit phenotype ${item.id}`}
                          onClick={() => setEditing(item)}
                        >
                          <Edit3 size={16} />
                        </button>
                        {role === 'admin' && (
                          <button
                            className="icon-button archive-button"
                            aria-label={`Archive phenotype ${item.id}`}
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
      {entry && (
        <PhenotypeForm
          studies={studies.data || []}
          close={() => setEntry(false)}
          saved={result.reload}
        />
      )}
      {editing && (
        <PhenotypeForm
          record={editing}
          studies={studies.data || []}
          close={() => setEditing(undefined)}
          saved={result.reload}
        />
      )}
      {archive && (
        <ConfirmDelete
          label="phenotype record"
          close={() => setArchive(undefined)}
          submit={async () => {
            await api(`/phenotypes/${archive.id}`, { method: 'DELETE' })
            result.reload()
          }}
        />
      )}
    </>
  )
}
