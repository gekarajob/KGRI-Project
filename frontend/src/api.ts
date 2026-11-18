export const TOKEN_KEY = 'kgri_access_token'
export class ApiError extends Error {
  field?: string
  details: { field: string; message: string }[]
  status: number
  constructor(
    message: string,
    status: number,
    field?: string,
    details: { field: string; message: string }[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.field = field
    this.details = details
    this.status = status
  }
}

export function query(params: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return search.size ? `?${search.toString()}` : ''
}

async function request(path: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY)
  const headers = new Headers(options.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers })
  } catch {
    throw new ApiError('The server could not be reached. Check your connection and try again.', 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = body.error || {}
    if (response.status === 401 && !path.endsWith('/login')) {
      sessionStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new Event('kgri-session-expired'))
    }
    throw new ApiError(
      error.message || 'The request could not be completed.',
      response.status,
      error.field,
      error.details || [],
    )
  }
  return response
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await request(path, options)
  return response.status === 204 ? (undefined as T) : response.json()
}

export function body(value: unknown) {
  return JSON.stringify(value)
}

export async function downloadCsv(path: string) {
  const response = await request(path)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = 'kgri-phenotypes.csv'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
