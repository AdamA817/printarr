/**
 * System API types (v0.7)
 */

export interface SyncActivity {
  channels_syncing: number
  backfills_running: number
  imports_syncing: number
}

export interface DownloadActivity {
  active: number
  queued: number
}

export interface ImageActivity {
  telegram_downloading: number
  previews_generating: number
}

export interface AnalysisActivity {
  archives_extracting: number
  importing_to_library: number
  analyzing_3mf: number
}

export interface ActivitySummary {
  total_active: number
  total_queued: number
  is_idle: boolean
}

export interface SystemActivityResponse {
  sync: SyncActivity
  downloads: DownloadActivity
  images: ImageActivity
  analysis: AnalysisActivity
  summary: ActivitySummary
}
