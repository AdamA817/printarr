// Event types matching backend app/services/events.py (#222)

export type EventType =
  // Job events
  | 'job_created'
  | 'job_started'
  | 'job_progress'
  | 'job_completed'
  | 'job_failed'
  | 'job_canceled'
  // Design events
  | 'design_status_changed'
  | 'design_created'
  | 'design_updated'
  | 'design_deleted'
  // Queue events
  | 'queue_updated'
  // System events
  | 'heartbeat'
  | 'sync_status'

// Event payloads
export interface JobCreatedPayload {
  job_id: string
  job_type: string
  design_id: string | null
  display_name: string | null
  priority: number
}

export interface JobStartedPayload {
  job_id: string
  job_type: string
  design_id: string | null
}

export interface JobProgressPayload {
  job_id: string
  progress: number | null
  progress_message: string | null
  current_file: string | null
  current_file_bytes: number | null
  current_file_total: number | null
}

export interface JobCompletedPayload {
  job_id: string
  job_type: string
  design_id: string | null
  result: Record<string, unknown> | null
}

export interface JobFailedPayload {
  job_id: string
  job_type: string
  design_id: string | null
  error: string | null
  will_retry: boolean
}

export interface JobCanceledPayload {
  job_id: string
  job_type: string
  design_id: string | null
}

export interface DesignStatusChangedPayload {
  design_id: string
  old_status: string | null
  new_status: string
  title: string | null
}

export interface DesignCreatedPayload {
  design_id: string
  title: string
  designer: string | null
}

export interface QueueUpdatedPayload {
  // Empty payload - signals to refetch queue
}

export interface HeartbeatPayload {
  message: string
  client_count?: number
}

export interface SyncStatusPayload {
  channel_id: string | null
  channel_title: string | null
  status: string
  new_designs: number
}

// Generic event structure
export interface SSEEvent<T = unknown> {
  type: EventType
  payload: T
  timestamp: string
}

// Connection status
export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
