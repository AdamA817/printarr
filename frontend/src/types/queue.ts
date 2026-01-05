// Must match backend/app/db/models/enums.py
export type JobType = 'DOWNLOAD_DESIGN' | 'EXTRACT_ARCHIVE' | 'IMPORT_FILES' | 'GENERATE_PREVIEW' | 'SYNC_IMPORT_SOURCE'
export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED'
export type JobPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT'

// Priority values for ordering
export const PRIORITY_VALUES: Record<JobPriority, number> = {
  LOW: 0,
  NORMAL: 5,
  HIGH: 10,
  URGENT: 20,
}

// Queue item from GET /api/v1/queue/
export interface QueueItem {
  id: string
  job_type: JobType
  status: JobStatus
  priority: number
  progress: number | null
  progress_message: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  design: QueueItemDesign | null
  import_source: QueueItemImportSource | null
}

// Simplified design info for queue display
export interface QueueItemDesign {
  id: string
  canonical_title: string
  canonical_designer: string
  channel_title: string | null
}

// Import source info for SYNC_IMPORT_SOURCE jobs
export interface QueueItemImportSource {
  id: string
  name: string
  source_type: string
}

// Queue list response
export interface QueueList {
  items: QueueItem[]
  total: number
}

// Queue stats from GET /api/v1/queue/stats
export interface QueueStats {
  queued: number
  downloading: number
  extracting: number
  importing: number
  total_active: number
}

// Result stats for completed jobs (#95)
export interface JobResultStats {
  // Download jobs
  files_downloaded?: number
  total_bytes?: number
  has_archives?: boolean
  // Extraction jobs
  archives_extracted?: number
  files_created?: number
  nested_archives?: number
  // Import jobs
  files_imported?: number
  library_path?: string
}

// Activity history item from GET /api/v1/activity/
// Note: inherits import_source from QueueItem
export interface ActivityItem extends QueueItem {
  duration_seconds: number | null
  result: JobResultStats | null
}

export interface ActivityList {
  items: ActivityItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Query params
export interface QueueListParams {
  status?: string
  job_type?: string
}

export interface ActivityListParams {
  page?: number
  page_size?: number
  status?: string
  job_type?: string
}
