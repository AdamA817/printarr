// Settings types for v0.5

export interface LibrarySettings {
  folder_template: string
  delete_archives_after_extraction: boolean
  max_concurrent_downloads: number
}

export interface SettingValue {
  key: string
  value: string | number | boolean
  description?: string
}

export interface SettingsMap {
  [key: string]: string | number | boolean
}

// Template variables available for folder template
export const TEMPLATE_VARIABLES = [
  { name: '{designer}', description: 'The design creator/author name' },
  { name: '{channel}', description: 'The channel/source name' },
  { name: '{title}', description: 'The design title (required)' },
  { name: '{date}', description: 'Full date (YYYY-MM-DD)' },
  { name: '{year}', description: 'Year (YYYY)' },
  { name: '{month}', description: 'Month (MM)' },
] as const

// Default values
export const DEFAULT_FOLDER_TEMPLATE = '{designer}/{title}'
export const DEFAULT_MAX_CONCURRENT_DOWNLOADS = 3
export const DEFAULT_DELETE_ARCHIVES = true
