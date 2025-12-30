// Must match backend/app/db/models/enums.py exactly
export type DesignStatus = 'DISCOVERED' | 'WANTED' | 'DOWNLOADING' | 'DOWNLOADED' | 'ORGANIZED'
export type MulticolorStatus = 'UNKNOWN' | 'SINGLE' | 'MULTI'

// Summary of channel info for design response
export interface ChannelSummary {
  id: string
  title: string
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

// Paginated design list response
export interface DesignList {
  items: DesignListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Query parameters for listing designs
export interface DesignListParams {
  page?: number
  page_size?: number
  status?: DesignStatus
  channel_id?: string
}
