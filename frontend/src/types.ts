export type Role = 'admin' | 'lab_tech' | 'field_officer'
export interface User {
  id: number
  username: string
  role: Role
  is_active: boolean
}
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
export interface Consent {
  broad_consent: boolean
  recontact_consent: boolean
  data_sharing_consent: boolean
  broad_consent_recorded_at?: string | null
  recontact_consent_recorded_at?: string | null
  data_sharing_consent_recorded_at?: string | null
}
export interface Participant {
  id: number
  kgri_id: string
  full_name: string
  age: number
  sex: string
  community: string
  county: string
  recruitment_site: string
  created_at: string
  consent: Consent
  samples?: Sample[]
  phenotypes?: Phenotype[]
  phenotypes_restricted?: boolean
}
export interface Sample {
  id: number
  participant_id: number
  kgri_id?: string
  participant_name?: string
  recruitment_site?: string
  sample_type: string
  status: string
  platform: string | null
  batch_id: string | null
  sequencing_file_path: string | null
  mean_coverage: number | null
  created_at: string
  allowed_next_states?: string[]
}
export interface Study {
  id: number
  code: string
  name: string
}
export interface Phenotype {
  id: number
  participant_id: number
  study_id: number
  kgri_id?: string
  participant_name?: string
  study_code?: string
  recruitment_site?: string
  captured_at: string
  height_cm: number
  weight_kg: number
  systolic_bp: number
  diastolic_bp: number
  malaria_history: boolean
  livestock_contact: boolean
  notes: string | null
}
export interface AuditEvent {
  id: number
  user_id: number
  username?: string
  occurred_at: string
  action: string
  entity_type: string
  entity_id: number
  changed_fields: Record<string, { old: unknown; new: unknown }>
}
export interface Summary {
  total: number
  by_status: { status: string; count: number }[]
  by_platform: { platform: string | null; count: number }[]
  by_site: { recruitment_site: string; count: number }[]
}
export const states = [
  'collected',
  'shipped',
  'received_at_lab',
  'dna_extracted',
  'library_prepped',
  'sequenced',
  'qc_passed',
]
export const platforms = ['ultima_ug100', 'ont_promethion', 'pacbio', 'olink']
export const label = (value: string) =>
  value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
export const roleLabel: Record<Role, string> = {
  admin: 'Administrator',
  lab_tech: 'Lab technician',
  field_officer: 'Field officer',
}
export const date = (value?: string | null) =>
  value
    ? new Date(value).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : 'Not recorded'
export const dateTime = (value: string) =>
  new Date(value).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
