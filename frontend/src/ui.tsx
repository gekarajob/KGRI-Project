import {
  cloneElement,
  useEffect,
  useId,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
} from 'react'
import { AlertCircle, ArrowLeft, ArrowRight, Check, LoaderCircle, Search, X } from 'lucide-react'
import { ApiError } from './api'
import type { Page } from './types'

export function useLoad<T>(loader: () => Promise<T>, dependencies: unknown[]) {
  const [data, setData] = useState<T>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true)
    setData(undefined)
    setError('')
    loader()
      .then((value) => {
        if (active) setData(value)
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
    // Each caller supplies the request inputs so obsolete responses are discarded.
  }, [...dependencies, revision])
  return { data, error, loading, reload: () => setRevision((value) => value + 1) }
}

export function Alert({ children, success = false }: { children: ReactNode; success?: boolean }) {
  if (!children) return null
  return (
    <div className={`alert ${success ? 'success' : ''}`} role={success ? 'status' : 'alert'}>
      {success ? <Check size={17} /> : <AlertCircle size={17} />}
      <span>{children}</span>
    </div>
  )
}

export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={23} />
      <span>Loading records…</span>
    </div>
  )
}
export function Empty({
  title = 'No records found',
  children,
}: {
  title?: string
  children?: ReactNode
}) {
  return (
    <div className="empty">
      <Search size={26} />
      <h3>{title}</h3>
      <p>{children || 'Try changing your search or filters.'}</p>
    </div>
  )
}
export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>
}
export function ConsentDot({ value }: { value: boolean }) {
  return (
    <span className={`consent-dot ${value ? 'yes' : ''}`} title={value ? 'Granted' : 'Not granted'}>
      {value ? <Check size={13} /> : <X size={12} />}
    </span>
  )
}
export function Field({
  label,
  children,
  hint,
  error,
}: {
  label: string
  children: ReactElement<
    Pick<HTMLAttributes<HTMLElement>, 'id' | 'aria-describedby' | 'aria-invalid'>
  >
  hint?: string
  error?: string
}) {
  const generatedId = useId()
  const id = children.props.id || generatedId
  const descriptionId = `${id}-description`
  const describedBy = [
    children.props['aria-describedby'],
    error || hint ? descriptionId : undefined,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <div className={`field ${error ? 'invalid' : ''}`}>
      <label htmlFor={id}>{label}</label>
      <div>
        {cloneElement(children, {
          id,
          'aria-describedby': describedBy || undefined,
          'aria-invalid': error ? true : children.props['aria-invalid'],
        })}
      </div>
      {error ? (
        <small id={descriptionId} className="field-error">
          {error}
        </small>
      ) : (
        hint && <small id={descriptionId}>{hint}</small>
      )}
    </div>
  )
}
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {}
  const errors: Record<string, string> = {}
  error.details.forEach((item) => {
    errors[item.field.replace(/^body\./, '')] = item.message
  })
  if (error.field) errors[error.field.replace(/^body\./, '')] = error.message
  return errors
}
let openModals = 0
let previousBodyOverflow = ''

export function Modal({
  title,
  subtitle,
  children,
  close,
  wide = false,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  close: () => void
  wide?: boolean
}) {
  const dialog = useRef<HTMLDivElement>(null)
  const latestClose = useRef(close)
  const titleId = useId()
  const subtitleId = useId()
  useEffect(() => {
    latestClose.current = close
  }, [close])
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const first =
      dialog.current?.querySelector<HTMLElement>(
        'input:not(:disabled),select:not(:disabled),textarea:not(:disabled)',
      ) || dialog.current?.querySelector<HTMLElement>('button:not(:disabled)')
    const initialFocus = first || dialog.current
    initialFocus?.focus()
    const onKey = (event: KeyboardEvent) => {
      const dialogs = document.querySelectorAll('[role="dialog"]')
      if (dialogs[dialogs.length - 1] !== dialog.current) return
      if (event.key === 'Escape') {
        event.preventDefault()
        latestClose.current()
      }
      if (event.key !== 'Tab') return
      const elements = Array.from(
        dialog.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]',
        ) || [],
      ).filter((element) => element.getClientRects().length > 0)
      if (!elements.length) {
        event.preventDefault()
        dialog.current?.focus()
        return
      }
      const start = elements[0]
      const end = elements[elements.length - 1]
      if (!dialog.current?.contains(document.activeElement)) {
        event.preventDefault()
        const target = event.shiftKey ? end : start
        target.focus()
      } else if (event.shiftKey && document.activeElement === start) {
        event.preventDefault()
        end.focus()
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault()
        start.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    if (openModals === 0) previousBodyOverflow = document.body.style.overflow
    openModals += 1
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      openModals -= 1
      if (openModals === 0) document.body.style.overflow = previousBodyOverflow
      if (previous?.isConnected) previous.focus()
    }
  }, [])
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close()
      }}
    >
      <div
        className={`modal ${wide ? 'wide' : ''}`}
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        tabIndex={-1}
      >
        <header>
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p id={subtitleId}>{subtitle}</p>}
          </div>
          <button type="button" className="icon-button" aria-label="Close dialog" onClick={close}>
            <X size={21} />
          </button>
        </header>
        {children}
      </div>
    </div>
  )
}
export function Pagination({
  data,
  page,
  setPage,
}: {
  data?: Page<unknown>
  page: number
  setPage: (page: number) => void
}) {
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  useEffect(() => {
    if (data && page > pages) setPage(pages)
  }, [data, page, pages, setPage])
  if (!data?.total || page > pages) return null
  return (
    <div className="pagination">
      <span>
        Showing {(page - 1) * data.page_size + 1}–{Math.min(page * data.page_size, data.total)} of{' '}
        {data.total} records
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Previous page"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          <ArrowLeft size={16} />
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button
          className="icon-button"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => setPage(page + 1)}
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
export function ConfirmDelete({
  label,
  submit,
  close,
}: {
  label: string
  submit: () => Promise<void>
  close: () => void
}) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <Modal title={`Archive ${label}?`} close={close}>
      <p className="modal-copy">
        This record will be removed from active views. Its history will be preserved in the audit
        log.
      </p>
      <Alert>{error}</Alert>
      <footer>
        <button className="button secondary" onClick={close}>
          Cancel
        </button>
        <button
          className="button danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true)
            try {
              await submit()
              close()
            } catch (reason) {
              setError((reason as Error).message)
              setBusy(false)
            }
          }}
        >
          {busy ? 'Archiving…' : 'Archive record'}
        </button>
      </footer>
    </Modal>
  )
}
