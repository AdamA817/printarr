/**
 * TypeScript types for Import Sources and Profiles (v0.8)
 * Must match backend/app/schemas/import_source.py and import_profile.py
 */

// =============================================================================
// Enums - Must match backend/app/db/models/enums.py
// =============================================================================

// Must match backend/app/db/models/enums.py
export type ImportSourceType = 'GOOGLE_DRIVE' | 'UPLOAD' | 'BULK_FOLDER' | 'PHPBB_FORUM'

export type ImportSourceStatus = 'ACTIVE' | 'PAUSED' | 'ERROR' | 'PENDING' | 'RATE_LIMITED'

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
// Import Source Folder Types (DEC-038)
// =============================================================================

export interface ImportSourceFolderSummary {
  id: string
  name: string | null
  google_drive_url: string | null
  google_folder_id: string | null
  folder_path: string | null
  phpbb_forum_url: string | null // v1.0 - issue #242
  enabled: boolean
  items_detected: number
  items_imported: number
  last_synced_at: string | null
  has_overrides: boolean
}

export interface ImportSourceFolder extends ImportSourceFolderSummary {
  import_source_id: string
  import_profile_id: string | null
  default_designer: string | null
  default_tags: string[] | null
  effective_profile_id: string | null
  effective_designer: string | null
  effective_tags: string[]
  sync_cursor: string | null
  last_sync_error: string | null
  created_at: string
  updated_at: string
}

export interface ImportSourceFolderCreate {
  name?: string | null
  google_drive_url?: string | null
  folder_path?: string | null
  phpbb_forum_url?: string | null // v1.0 - issue #242
  import_profile_id?: string | null
  default_designer?: string | null
  default_tags?: string[] | null
  enabled?: boolean
}

export interface ImportSourceFolderUpdate {
  name?: string | null
  import_profile_id?: string | null
  default_designer?: string | null
  default_tags?: string[] | null
  enabled?: boolean | null
}

// =============================================================================
// Import Source Types
// =============================================================================

export interface ImportSource {
  id: string
  name: string
  source_type: ImportSourceType
  status: ImportSourceStatus

  // Google OAuth status (shared across all folders)
  google_connected?: boolean

  // phpBB connection status (v1.0 - issue #241)
  phpbb_connected?: boolean
  phpbb_forum_url?: string | null

  // Type-specific fields (DEPRECATED - use folders instead)
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

  // Multi-folder support (DEC-038)
  folder_count: number
  folders: ImportSourceFolderSummary[]
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
  google_credentials_id?: string | null

  // Bulk folder specific
  folder_path?: string | null

  // phpBB specific (v1.0 - issue #241)
  phpbb_credentials_id?: string | null
  phpbb_forum_url?: string | null

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
  api_key_configured: boolean
  authenticated: boolean
  email: string | null
  expires_at: string | null
}

export interface GoogleCredentials {
  id: string
  email: string
  expires_at: string | null
  created_at: string
  updated_at: string
}

export interface GoogleCredentialsList {
  items: GoogleCredentials[]
  total: number
}

export interface GoogleOAuthInitResponse {
  authorization_url: string
  state: string
}

export interface GoogleOAuthCallbackParams {
  code: string
  state: string
}

export interface GoogleOAuthCallbackResponse {
  success: boolean
  credentials_id: string
  email: string
  message: string
}

// =============================================================================
// phpBB Credentials Types (v1.0 - issue #241)
// =============================================================================

export interface PhpbbTestLoginRequest {
  base_url: string
  username: string
  password: string
}

export interface PhpbbTestLoginResponse {
  success: boolean
  message: string
}

export interface PhpbbCredentialsCreate {
  base_url: string
  username: string
  password: string
  test_login?: boolean
}

export interface PhpbbCredentials {
  id: string
  base_url: string
  last_login_at: string | null
  last_login_error: string | null
  session_expires_at: string | null
  created_at: string
}

export interface PhpbbCredentialsList {
  items: PhpbbCredentials[]
}
