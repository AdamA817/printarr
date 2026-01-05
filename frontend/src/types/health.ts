// Health API types (DEC-042)

export type SubsystemStatus = 'healthy' | 'degraded' | 'unhealthy'
export type OverallStatus = 'healthy' | 'degraded' | 'unhealthy'

export interface DatabaseStatus {
  status: SubsystemStatus
  latency_ms: number | null
}

export interface TelegramStatus {
  status: SubsystemStatus
  connected: boolean
  authenticated: boolean
}

export interface WorkersStatus {
  status: SubsystemStatus
  jobs_queued: number
  jobs_running: number
  jobs_failed_24h: number
}

export interface StorageStatus {
  status: SubsystemStatus
  library_gb: number
  staging_gb: number
  cache_gb: number
  library_free_gb: number
}

export interface RateLimiterStatus {
  status: SubsystemStatus
  requests_total: number
  throttled_count: number
  channels_in_backoff: number
}

export interface Subsystems {
  database: DatabaseStatus
  telegram: TelegramStatus
  workers: WorkersStatus
  storage: StorageStatus
  rate_limiter: RateLimiterStatus
}

export interface RecentError {
  job_id: string
  job_type: string
  error: string
  timestamp: string
}

export interface DetailedHealthResponse {
  overall: OverallStatus
  version: string
  subsystems: Subsystems
  errors: RecentError[]
}
