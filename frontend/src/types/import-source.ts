/**
 * TypeScript types for Import Sources and Profiles (v0.8)
 * Must match backend/app/schemas/import_source.py and import_profile.py
 */

// =============================================================================
// Enums - Must match backend/app/db/models/enums.py
// =============================================================================

export type ImportSourceType = 'GOOGLE_DRIVE' | 'UPLOAD' | 'BULK_FOLDER'

export type ImportSourceStatus = 'ACTIVE' | 'PAUSED' | 'ERROR' | 'PENDING'

export type ImportRecordStatus = 'PENDING' | 'IMPORTING' | 'IMPORTED' | 'SKIPPED' | 'ERROR'

export type ConflictResolution = 'SKIP' | 'REPLACE' | 'ASK'

// =============================================================================
// Import Profile Configuration Types
// =============================================================================

export interface ProfileDetectionConfig {
  model_extensions: string[]
  archive_extensions: string[]
  min_model_files: number
  structure: 'nested' | 'flat' | 'auto'
  model_subfolders: string[]
}

export interface ProfileTitleConfig {
  source: 'folder_name' | 'parent_folder' | 'filename'
  strip_patterns: string[]
  case_transform: 'none' | 'title' | 'lower' | 'upper'
}

export interface ProfilePreviewConfig {
  folders: string[]
  wildcard_folders: string[]
  extensions: string[]
  include_root: boolean
}

export interface ProfileIgnoreConfig {
  folders: string[]
  extensions: string[]
  patterns: string[]
}

export interface ProfileAutoTagConfig {
  from_subfolders: boolean
  from_filename: boolean
  subfolder_levels: number
  strip_patterns: string[]
}

export interface ImportProfileConfig {
  detection: ProfileDetectionConfig
  title: ProfileTitleConfig
  preview: ProfilePreviewConfig
  ignore: ProfileIgnoreConfig
  auto_tags: ProfileAutoTagConfig
}

// =============================================================================
// Import Profile Types
// =============================================================================

export interface ImportProfileSummary {
  id: string
  name: string
  is_builtin: boolean
}

export interface ImportProfile {
  id: string
  name: string
  description: string | null
  is_builtin: boolean
  config: ImportProfileConfig
  created_at: string
  updated_at: string
}

export interface ImportProfileCreate {
  name: string
  description?: string | null
  config?: ImportProfileConfig
}

export interface ImportProfileUpdate {
  name?: string
  description?: string | null
  config?: ImportProfileConfig
}

export interface ImportProfileList {
  items: ImportProfile[]
  total: number
}

export interface ImportProfileUsage {
  sources_using: number
  source_names: string[]
}

// =============================================================================
// Import Source Types
// =============================================================================

export interface ImportSource {
  id: string
  name: string
  source_type: ImportSourceType
  status: ImportSourceStatus

  // Type-specific fields
  google_drive_url: string | null
  google_drive_folder_id: string | null
  folder_path: string | null

  // Settings
  import_profile_id: string | null
  default_designer: string | null
  default_tags: string[] | null
  sync_enabled: boolean
  sync_interval_hours: number

  // State
  last_sync_at: string | null
  last_sync_error: string | null
  items_imported: number

  // Timestamps
  created_at: string
  updated_at: string

  // Embedded profile (optional)
  profile: ImportProfileSummary | null
}

export interface ImportSourceDetail extends ImportSource {
  pending_count: number
  imported_count: number
  error_count: number
}

export interface ImportSourceCreate {
  name: string
  source_type: ImportSourceType

  // Google Drive specific
  google_drive_url?: string | null

  // Bulk folder specific
  folder_path?: string | null

  // Optional settings
  import_profile_id?: string | null
  default_designer?: string | null
  default_tags?: string[] | null
  sync_enabled?: boolean
  sync_interval_hours?: number
}

export interface ImportSourceUpdate {
  name?: string

  // Type-specific (cannot change source_type)
  google_drive_url?: string | null
  folder_path?: string | null

  // Settings
  import_profile_id?: string | null
  default_designer?: string | null
  default_tags?: string[] | null
  sync_enabled?: boolean | null
  sync_interval_hours?: number | null
}

export interface ImportSourceList {
  items: ImportSource[]
  total: number
}

export interface ImportSourceListParams {
  source_type?: ImportSourceType
  sync_enabled?: boolean
  status?: ImportSourceStatus
  page?: number
  page_size?: number
}

// =============================================================================
// Sync & History Types
// =============================================================================

export interface SyncTriggerRequest {
  conflict_resolution?: ConflictResolution
  auto_import?: boolean
}

export interface SyncTriggerResponse {
  source_id: string
  job_id: string | null
  message: string
  designs_detected: number
  designs_imported: number
}

export interface ImportHistoryItem {
  id: string
  source_path: string
  status: ImportRecordStatus
  detected_title: string | null
  design_id: string | null
  error_message: string | null
  detected_at: string
  imported_at: string | null
}

export interface ImportHistoryResponse {
  items: ImportHistoryItem[]
  total: number
  page: number
  page_size: number
}

export interface ImportHistoryParams {
  status?: ImportRecordStatus
  page?: number
  page_size?: number
}

// =============================================================================
// Google OAuth Types
// =============================================================================

export interface GoogleOAuthStatus {
  configured: boolean
  authenticated: boolean
  email: string | null
  expires_at: string | null
}
