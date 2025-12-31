// Dashboard types (v0.6)
// Must match backend/app/schemas/stats.py

export interface DesignStatusCounts {
  discovered: number
  wanted: number
  downloading: number
  downloaded: number
  imported: number
  failed: number
  total: number
}

export interface ChannelCounts {
  enabled: number
  disabled: number
  total: number
}

export interface DownloadStats {
  today: number
  this_week: number
  active: number
  queued: number
}

export interface DashboardStatsResponse {
  designs: DesignStatusCounts
  channels: ChannelCounts
  discovered_channels: number
  downloads: DownloadStats
  library_file_count: number
  library_size_bytes: number
}

export interface CalendarDesign {
  id: string
  title: string
  thumbnail_url: string | null
}

export interface CalendarDay {
  date: string
  count: number
  designs: CalendarDesign[]
}

export interface CalendarResponse {
  days: CalendarDay[]
  total_period: number
}

export interface JobSummary {
  id: string
  type: string
  status: string
  design_title: string | null
  created_at: string
  finished_at: string | null
  error: string | null
}

export interface QueueResponse {
  running: number
  queued: number
  recent_completions: JobSummary[]
  recent_failures: JobSummary[]
}

export interface StorageResponse {
  library_size_bytes: number
  staging_size_bytes: number
  cache_size_bytes: number
  available_bytes: number
  total_bytes: number
}
