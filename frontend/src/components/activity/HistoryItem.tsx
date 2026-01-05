import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ActivityItem, JobStatus } from '@/types/queue'
import { useRemoveActivity, useRetryJob } from '@/hooks/useQueue'

interface HistoryItemProps {
  item: ActivityItem
}

// Status badge colors
const statusColors: Record<JobStatus, string> = {
  QUEUED: 'bg-text-muted text-text-primary',
  RUNNING: 'bg-accent-primary text-white',
  SUCCESS: 'bg-accent-success text-white',
  FAILED: 'bg-accent-danger text-white',
  CANCELLED: 'bg-text-muted text-text-primary',
}

const statusIcons: Record<JobStatus, string> = {
  QUEUED: '⏳',
  RUNNING: '▶',
  SUCCESS: '✓',
  FAILED: '✗',
  CANCELLED: '⊘',
}

// Job type display names
const jobTypeLabels: Record<string, string> = {
  DOWNLOAD_DESIGN: 'Download',
  EXTRACT_ARCHIVE: 'Extract',
  IMPORT_FILES: 'Import',
  GENERATE_PREVIEW: 'Preview',
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '--'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || bytes === 0) return '--'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatSpeed(bytes: number | null | undefined, seconds: number | null): string {
  if (!bytes || !seconds || seconds === 0) return '--'
  const bytesPerSecond = bytes / seconds
  if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`
  if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`
}

function formatTimestamp(dateString: string | null): string {
  if (!dateString) return '--'
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Icon components
function CubeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  )
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  )
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`animate-spin ${className}`}
    >
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" strokeOpacity="1" />
    </svg>
  )
}

export function HistoryItem({ item }: HistoryItemProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const removeActivity = useRemoveActivity()
  const retryJob = useRetryJob()

  const isFailed = item.status === 'FAILED'
  const isCancelled = item.status === 'CANCELLED'
  const canRetry = isFailed || isCancelled

  // Get error message (prefer last_error over error_message)
  const errorMessage = item.last_error || item.error_message

  // Format retry info
  const retryInfo = item.attempts !== null && item.max_attempts !== null
    ? `Attempt ${item.attempts}/${item.max_attempts}`
    : null

  const handleRetry = async () => {
    try {
      await retryJob.mutateAsync(item.id)
    } catch (error) {
      console.error('Failed to retry job:', error)
    }
  }

  const handleRemove = async () => {
    try {
      await removeActivity.mutateAsync(item.id)
    } catch (error) {
      console.error('Failed to remove from history:', error)
    }
  }

  return (
    <div className={`bg-bg-secondary rounded-lg overflow-hidden ${isFailed ? 'ring-1 ring-accent-danger/30' : ''}`}>
      <div className="p-4">
        <div className="flex items-start gap-4">
          {/* Thumbnail/Icon */}
          <div className="w-10 h-10 bg-bg-tertiary rounded-lg flex items-center justify-center flex-shrink-0">
            <CubeIcon className="w-5 h-5 text-text-muted" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                {/* Title */}
                {item.design ? (
                  <Link
                    to={`/designs/${item.design.id}`}
                    className="text-text-primary font-medium hover:text-accent-primary transition-colors block truncate"
                  >
                    {item.design.canonical_title}
                  </Link>
                ) : (
                  <span className="text-text-primary font-medium">Unknown Design</span>
                )}

                {/* Designer & Job Type */}
                <div className="flex items-center gap-2 text-sm text-text-secondary mt-0.5">
                  {item.design?.canonical_designer && (
                    <span>by {item.design.canonical_designer}</span>
                  )}
                  <span className="text-text-muted">•</span>
                  <span>{jobTypeLabels[item.job_type] || item.job_type}</span>
                </div>
              </div>

              {/* Status badge */}
              <div className="flex items-center gap-2">
                <span className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 ${statusColors[item.status]}`}>
                  <span>{statusIcons[item.status]}</span>
                  {item.status === 'SUCCESS' ? 'Completed' : item.status === 'FAILED' ? 'Failed' : item.status}
                </span>
                {/* DEC-042: Show retry info for failed jobs */}
                {isFailed && retryInfo && (
                  <span className="text-xs text-text-muted">{retryInfo}</span>
                )}
              </div>
            </div>

            {/* Meta info */}
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
              <span>{formatTimestamp(item.completed_at)}</span>
              {item.duration_seconds !== null && (
                <>
                  <span>•</span>
                  <span>Duration: {formatDuration(item.duration_seconds)}</span>
                </>
              )}
              {/* Result stats based on job type */}
              {item.result && item.status === 'SUCCESS' && (
                <>
                  {/* Download job stats */}
                  {item.job_type === 'DOWNLOAD_DESIGN' && item.result.total_bytes && (
                    <>
                      <span>•</span>
                      <span>{formatFileSize(item.result.total_bytes)}</span>
                      <span>•</span>
                      <span>{formatSpeed(item.result.total_bytes, item.duration_seconds)}</span>
                      {item.result.files_downloaded && (
                        <>
                          <span>•</span>
                          <span>{item.result.files_downloaded} file{item.result.files_downloaded !== 1 ? 's' : ''}</span>
                        </>
                      )}
                    </>
                  )}
                  {/* Extraction job stats */}
                  {item.job_type === 'EXTRACT_ARCHIVE' && (
                    <>
                      {item.result.archives_extracted && (
                        <>
                          <span>•</span>
                          <span>{item.result.archives_extracted} archive{item.result.archives_extracted !== 1 ? 's' : ''}</span>
                        </>
                      )}
                      {item.result.files_created && (
                        <>
                          <span>•</span>
                          <span>{item.result.files_created} file{item.result.files_created !== 1 ? 's' : ''} extracted</span>
                        </>
                      )}
                    </>
                  )}
                  {/* Import job stats */}
                  {item.job_type === 'IMPORT_FILES' && (
                    <>
                      {item.result.files_imported && (
                        <>
                          <span>•</span>
                          <span>{item.result.files_imported} file{item.result.files_imported !== 1 ? 's' : ''} imported</span>
                        </>
                      )}
                      {item.result.total_bytes && (
                        <>
                          <span>•</span>
                          <span>{formatFileSize(item.result.total_bytes)}</span>
                        </>
                      )}
                    </>
                  )}
                </>
              )}
            </div>

            {/* Error preview (for failed jobs) */}
            {isFailed && errorMessage && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="mt-2 flex items-center gap-1 text-xs text-accent-danger hover:text-accent-danger/80 transition-colors"
              >
                <ChevronDownIcon className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                {isExpanded ? 'Hide error' : 'Show error'}
              </button>
            )}

            {/* Actions row */}
            <div className="mt-3 flex items-center gap-2">
              {/* Retry button (for failed/cancelled jobs) - DEC-042 */}
              {canRetry && (
                <button
                  onClick={handleRetry}
                  disabled={retryJob.isPending}
                  className="text-xs px-2 py-1 rounded bg-accent-primary/20 text-accent-primary hover:bg-accent-primary/30 transition-colors disabled:opacity-50 flex items-center gap-1"
                >
                  {retryJob.isPending ? (
                    <LoadingSpinner className="w-3 h-3" />
                  ) : (
                    <RefreshIcon className="w-3 h-3" />
                  )}
                  Retry
                </button>
              )}

              {/* Remove button */}
              <button
                onClick={handleRemove}
                disabled={removeActivity.isPending}
                className="text-xs px-2 py-1 rounded bg-bg-tertiary text-text-muted hover:text-text-primary hover:bg-bg-tertiary/80 transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                <TrashIcon className="w-3 h-3" />
                Remove
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Expanded error details */}
      {isExpanded && isFailed && errorMessage && (
        <div className="px-4 pb-4">
          <div className="bg-accent-danger/10 border border-accent-danger/20 rounded p-3">
            <p className="text-sm text-accent-danger font-mono whitespace-pre-wrap">
              {errorMessage}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
