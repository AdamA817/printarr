import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { QueueItem as QueueItemType, JobStatus } from '@/types/queue'
import { useCancelJob, useUpdateJobPriority } from '@/hooks/useQueue'

interface QueueItemProps {
  item: QueueItemType
  position?: number
}

// Status badge colors
const statusColors: Record<JobStatus, string> = {
  QUEUED: 'bg-text-muted text-text-primary',
  RUNNING: 'bg-accent-primary text-white',
  SUCCESS: 'bg-accent-success text-white',
  FAILED: 'bg-accent-danger text-white',
  CANCELLED: 'bg-text-muted text-text-primary',
}

const statusLabels: Record<JobStatus, string> = {
  QUEUED: 'Queued',
  RUNNING: 'Running',
  SUCCESS: 'Success',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
}

// Job type display names
const jobTypeLabels: Record<string, string> = {
  DOWNLOAD_DESIGN: 'Downloading',
  EXTRACT_ARCHIVE: 'Extracting',
  IMPORT_FILES: 'Importing',
  GENERATE_PREVIEW: 'Generating Preview',
  SYNC_IMPORT_SOURCE: 'Syncing',
}

// Priority options
const PRIORITY_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: 'Low' },
  { value: 5, label: 'Normal' },
  { value: 10, label: 'High' },
  { value: 20, label: 'Urgent' },
]

function getPriorityLabel(priority: number): string {
  const option = PRIORITY_OPTIONS.find(o => o.value === priority)
  return option?.label || `Priority ${priority}`
}

function getPriorityColor(priority: number): string {
  if (priority >= 20) return 'text-accent-danger'
  if (priority >= 10) return 'text-accent-warning'
  if (priority >= 5) return 'text-text-primary'
  return 'text-text-muted'
}

function formatElapsedTime(startedAt: string | null): string {
  if (!startedAt) return '--'
  const start = new Date(startedAt)
  const now = new Date()
  const diffMs = now.getTime() - start.getTime()
  const seconds = Math.floor(diffMs / 1000)

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

function XIcon({ className }: { className?: string }) {
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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
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

function SyncIcon({ className }: { className?: string }) {
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
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  )
}

export function QueueItem({ item, position }: QueueItemProps) {
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [isChangingPriority, setIsChangingPriority] = useState(false)
  const [, setTick] = useState(0) // Force re-render for elapsed time

  const cancelJob = useCancelJob()
  const updatePriority = useUpdateJobPriority()

  // Update elapsed time every second when job is running
  useEffect(() => {
    if (item.status !== 'RUNNING') return
    const interval = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(interval)
  }, [item.status])

  const handleCancel = async () => {
    try {
      await cancelJob.mutateAsync(item.id)
      setShowCancelConfirm(false)
    } catch (error) {
      console.error('Failed to cancel job:', error)
    }
  }

  const handlePriorityChange = async (newPriority: number) => {
    setIsChangingPriority(true)
    try {
      await updatePriority.mutateAsync({ jobId: item.id, priority: newPriority })
    } catch (error) {
      console.error('Failed to update priority:', error)
    } finally {
      setIsChangingPriority(false)
    }
  }

  const isActive = item.status === 'RUNNING'
  const isQueued = item.status === 'QUEUED'
  const isSyncJob = item.job_type === 'SYNC_IMPORT_SOURCE'

  // Determine what to display based on job type
  const getTitle = () => {
    if (isSyncJob && item.import_source) {
      return item.import_source.name
    }
    if (item.design) {
      return item.design.canonical_title
    }
    // Use display_name as fallback for jobs without design (e.g., DOWNLOAD_IMPORT_RECORD)
    if (item.display_name) {
      // display_name format: "Download: Design Name from Source" - extract design name
      const match = item.display_name.match(/^Download:\s*(.+?)(?:\s+from\s+|$)/)
      if (match) {
        return match[1]
      }
      return item.display_name
    }
    return 'Unknown'
  }

  const getSubtitle = () => {
    if (isSyncJob && item.import_source) {
      const typeLabel = item.import_source.source_type === 'GOOGLE_DRIVE' ? 'Google Drive' : 'Folder'
      return `Import Source (${typeLabel})`
    }
    if (item.design) {
      const parts = []
      if (item.design.canonical_designer) {
        parts.push(`by ${item.design.canonical_designer}`)
      }
      if (item.design.channel_title) {
        parts.push(item.design.channel_title)
      }
      return parts.join(' • ')
    }
    return ''
  }

  return (
    <div className={`bg-bg-secondary rounded-lg p-4 ${isActive ? 'ring-1 ring-accent-primary/30' : ''}`}>
      <div className="flex items-start gap-4">
        {/* Thumbnail/Icon */}
        <div className="w-12 h-12 bg-bg-tertiary rounded-lg flex items-center justify-center flex-shrink-0">
          {isActive ? (
            <LoadingSpinner className="w-6 h-6 text-accent-primary" />
          ) : isSyncJob ? (
            <SyncIcon className="w-6 h-6 text-text-muted" />
          ) : (
            <CubeIcon className="w-6 h-6 text-text-muted" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              {/* Title */}
              {item.design && !isSyncJob ? (
                <Link
                  to={`/designs/${item.design.id}`}
                  className="text-text-primary font-medium hover:text-accent-primary transition-colors block truncate"
                >
                  {getTitle()}
                </Link>
              ) : isSyncJob && item.import_source ? (
                <Link
                  to="/settings/imports"
                  className="text-text-primary font-medium hover:text-accent-primary transition-colors block truncate"
                >
                  {getTitle()}
                </Link>
              ) : (
                <span className="text-text-primary font-medium">{getTitle()}</span>
              )}

              {/* Subtitle */}
              {getSubtitle() && (
                <div className="flex items-center gap-2 text-sm text-text-secondary mt-0.5">
                  <span>{getSubtitle()}</span>
                </div>
              )}
            </div>

            {/* Status & Position */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {position !== undefined && isQueued && (
                <span className="text-xs text-text-muted">#{position}</span>
              )}
              <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[item.status]}`}>
                {jobTypeLabels[item.job_type] || statusLabels[item.status]}
              </span>
            </div>
          </div>

          {/* Progress bar (for active jobs) */}
          {isActive && (
            <div className="mt-3 space-y-1">
              <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-primary rounded-full transition-all duration-300"
                  style={{ width: `${item.progress ?? 0}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-text-muted">
                <span>{item.progress_message || 'Processing...'}</span>
                <div className="flex items-center gap-2">
                  <span>{formatElapsedTime(item.started_at)}</span>
                  <span className="text-text-muted/50">•</span>
                  <span>{item.progress !== null ? `${item.progress}%` : '--'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Actions row */}
          <div className="mt-3 flex items-center gap-3">
            {/* Priority selector */}
            {isQueued && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Priority:</span>
                <select
                  value={item.priority}
                  onChange={(e) => handlePriorityChange(Number(e.target.value))}
                  disabled={isChangingPriority}
                  className={`text-xs px-2 py-1 rounded bg-bg-tertiary border-none focus:ring-1 focus:ring-accent-primary ${getPriorityColor(item.priority)}`}
                >
                  {PRIORITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Priority badge (for active jobs) */}
            {isActive && item.priority !== 5 && (
              <span className={`text-xs ${getPriorityColor(item.priority)}`}>
                {getPriorityLabel(item.priority)} Priority
              </span>
            )}

            {/* Cancel button */}
            {(isQueued || isActive) && (
              <button
                onClick={() => setShowCancelConfirm(true)}
                disabled={cancelJob.isPending}
                className="ml-auto text-xs px-2 py-1 rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                <XIcon className="w-3 h-3" />
                Cancel
              </button>
            )}
          </div>

          {/* Cancel confirmation */}
          {showCancelConfirm && (
            <div className="mt-3 p-3 bg-bg-tertiary rounded-lg">
              <p className="text-sm text-text-primary mb-2">
                Cancel this download?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleCancel}
                  disabled={cancelJob.isPending}
                  className="text-xs px-3 py-1.5 rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
                >
                  {cancelJob.isPending ? 'Cancelling...' : 'Yes, Cancel'}
                </button>
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="text-xs px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
                >
                  Keep
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
