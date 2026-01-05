// Settings types for v1.0 (#226)

// All settings from backend (#221)
export interface AllSettings {
  // Library settings
  library_template: string
  delete_archives_after_extraction: boolean
  max_concurrent_downloads: number
  // Telegram settings
  telegram_rate_limit_rpm: number
  telegram_channel_spacing: number
  // Sync settings
  sync_enabled: boolean
  sync_poll_interval: number
  sync_batch_size: number
  // Upload settings
  upload_max_size_mb: number
  upload_retention_hours: number
  // Preview/Render settings
  auto_queue_render_after_import: boolean
  auto_queue_render_priority: number
  // Google Drive settings
  google_request_delay: number
  google_requests_per_minute: number
}

// Backwards-compatible type alias
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

// New default values (#226)
export const DEFAULT_TELEGRAM_RATE_LIMIT = 30
export const DEFAULT_TELEGRAM_CHANNEL_SPACING = 2.0
export const DEFAULT_SYNC_ENABLED = true
export const DEFAULT_SYNC_POLL_INTERVAL = 300
export const DEFAULT_SYNC_BATCH_SIZE = 100
export const DEFAULT_UPLOAD_MAX_SIZE = 500
export const DEFAULT_UPLOAD_RETENTION = 24
export const DEFAULT_AUTO_QUEUE_RENDER = true
export const DEFAULT_RENDER_PRIORITY = -1
export const DEFAULT_GOOGLE_REQUEST_DELAY = 0.5
export const DEFAULT_GOOGLE_RPM = 60
