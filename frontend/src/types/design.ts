// Must match backend/app/db/models/enums.py exactly
export type DesignStatus = 'DISCOVERED' | 'WANTED' | 'DOWNLOADING' | 'DOWNLOADED' | 'EXTRACTING' | 'EXTRACTED' | 'IMPORTING' | 'ORGANIZED' | 'FAILED'
export type MulticolorStatus = 'UNKNOWN' | 'SINGLE' | 'MULTI'
export type MetadataAuthority = 'TELEGRAM' | 'THANGS' | 'PRINTABLES' | 'USER'
export type ExternalSourceType = 'THANGS' | 'PRINTABLES' | 'THINGIVERSE'
export type MatchMethod = 'LINK' | 'TEXT' | 'GEOMETRY' | 'MANUAL'

// Summary of channel info for design response
export interface ChannelSummary {
  id: string
  title: string
}

// Design source (from Telegram messages)
export interface DesignSource {
  id: string
  channel_id: string
  message_id: string
  source_rank: number
  is_preferred: boolean
  caption_snapshot: string | null
  created_at: string
  channel: ChannelSummary
}

// External metadata (e.g., Thangs link)
export interface ExternalMetadata {
  id: string
  source_type: ExternalSourceType
  external_id: string
  external_url: string
  confidence_score: number
  match_method: MatchMethod
  is_user_confirmed: boolean
  fetched_title: string | null
  fetched_designer: string | null
  fetched_tags: string | null
  last_fetched_at: string | null
  created_at: string
}

// Design list item (from GET /api/v1/designs/)
export interface DesignListItem {
  id: string
  canonical_title: string
  canonical_designer: string
  status: DesignStatus
  multicolor: MulticolorStatus
  file_types: string[]
  created_at: string
  updated_at: string
  channel: ChannelSummary | null
  has_thangs_link: boolean
}

// Design detail (from GET /api/v1/designs/{id})
export interface DesignDetail {
  id: string
  canonical_title: string
  canonical_designer: string
  status: DesignStatus
  multicolor: MulticolorStatus
  primary_file_types: string | null
  total_size_bytes: number | null
  title_override: string | null
  designer_override: string | null
  multicolor_override: MulticolorStatus | null
  notes: string | null
  metadata_authority: MetadataAuthority
  metadata_confidence: number | null
  display_title: string
  display_designer: string
  display_multicolor: MulticolorStatus
  created_at: string
  updated_at: string
  sources: DesignSource[]
  external_metadata: ExternalMetadata[]
}

// Paginated design list response
export interface DesignList {
  items: DesignListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Sort field options (must match backend SortField enum)
export type SortField = 'created_at' | 'canonical_title' | 'canonical_designer' | 'total_size_bytes'
export type SortOrder = 'ASC' | 'DESC'

// Query parameters for listing designs (must match backend API)
export interface DesignListParams {
  page?: number
  page_size?: number
  status?: DesignStatus
  channel_id?: string
  file_type?: string
  multicolor?: MulticolorStatus
  has_thangs_link?: boolean
  designer?: string
  q?: string // Full-text search on title and designer
  sort_by?: SortField
  sort_order?: SortOrder
}

// Request/Response types for Thangs link operations
export interface ThangsLinkRequest {
  model_id: string
  url: string
}

export interface ThangsLinkByUrlRequest {
  url: string
}

export interface ThangsLinkResponse {
  id: string
  design_id: string
  source_type: string
  external_id: string
  external_url: string
  confidence_score: number
  match_method: string
  is_user_confirmed: boolean
  fetched_title: string | null
  fetched_designer: string | null
  fetched_tags: string | null
  last_fetched_at: string | null
  created_at: string
}

export interface RefreshMetadataResponse {
  design_id: string
  sources_refreshed: number
  sources_failed: number
}

// Request types for design update
export interface DesignUpdateRequest {
  title_override?: string | null
  designer_override?: string | null
  multicolor_override?: MulticolorStatus | null
  notes?: string | null
  status?: DesignStatus
}

// Thangs search types
export interface ThangsSearchResult {
  model_id: string
  title: string
  designer: string | null
  thumbnail_url: string | null
  url: string
}

export interface ThangsSearchResponse {
  results: ThangsSearchResult[]
  total: number
}

// Merge/Unmerge types
export interface MergeDesignsRequest {
  source_design_ids: string[]
}

export interface MergeDesignsResponse {
  merged_design_id: string
  merged_source_count: number
  deleted_design_ids: string[]
}

export interface UnmergeDesignRequest {
  source_ids: string[]
}

export interface UnmergeDesignResponse {
  original_design_id: string
  new_design_id: string
  moved_source_count: number
}

// Download action types (for v0.5 download workflow)
export interface WantDesignResponse {
  design_id: string
  status: DesignStatus
  job_id: string | null
}

export interface DownloadDesignResponse {
  design_id: string
  status: DesignStatus
  job_id: string
}

export interface CancelDownloadResponse {
  design_id: string
  status: DesignStatus
  cancelled_job_id: string | null
}
