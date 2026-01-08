// Upload API types (#179)
// Must match backend/app/schemas/upload.py

export type UploadStatusType = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'EXPIRED'

// Response from POST /api/v1/upload/files
export interface UploadResponse {
  upload_id: string
  filename: string
  size: number
  status: UploadStatusType
}

// Response from POST /api/v1/upload/files/batch
export interface BatchUploadResponse {
  batch_id: string
  uploads: UploadResponse[]
  total_size: number
}

// Response from GET /api/v1/upload/{upload_id}/status
export interface UploadStatusResponse {
  upload_id: string
  filename: string
  status: UploadStatusType
  error_message: string | null
  design_id: string | null
  progress: number
}

// Request body for POST /api/v1/upload/{upload_id}/process
export interface ProcessUploadRequest {
  import_profile_id?: string
  designer?: string
  tags?: string[]
  title?: string
}

// Response from POST /api/v1/upload/{upload_id}/process
export interface ProcessUploadResponse {
  upload_id: string
  status: UploadStatusType
  design_id: string | null
  design_title: string | null
  files_extracted: number
  model_files: number
  preview_files: number
  error_message: string | null
}
