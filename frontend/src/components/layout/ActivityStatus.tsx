/**
 * ActivityStatus - Sidebar activity indicator
 *
 * Shows actual jobs with names and progress bars:
 * - Downloads (active/queued)
 * - Extracting archives
 * - Importing files
 * - Syncing sources
 */
import { useState, useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import { useQueue } from '@/hooks/useQueue'
import type { QueueItem, JobType } from '@/types/queue'

// Persist expanded state in localStorage
const EXPANDED_KEY = 'printarr:activity-expanded'

function getInitialExpanded(): boolean {
  try {
    const stored = localStorage.getItem(EXPANDED_KEY)
    return stored === 'true'
  } catch {
    return false
  }
}

// Get display name for a job
function getJobDisplayName(job: QueueItem): string {
  if (job.display_name) return job.display_name
  if (job.design?.canonical_title) return job.design.canonical_title
  if (job.import_source?.name) return job.import_source.name
  return 'Unknown job'
}

// Get job type label
function getJobTypeLabel(jobType: JobType): string {
  switch (jobType) {
    case 'DOWNLOAD_DESIGN':
      return 'Downloading'
    case 'EXTRACT_ARCHIVE':
      return 'Extracting'
    case 'IMPORT_FILES':
      return 'Importing'
    case 'GENERATE_PREVIEW':
      return 'Generating preview'
    case 'SYNC_IMPORT_SOURCE':
      return 'Syncing'
    default:
      return 'Processing'
  }
}

// Get icon for job type
function getJobTypeIcon(jobType: JobType): React.ReactNode {
  switch (jobType) {
    case 'DOWNLOAD_DESIGN':
      return <DownloadIcon className="w-3.5 h-3.5" />
    case 'EXTRACT_ARCHIVE':
      return <ArchiveIcon className="w-3.5 h-3.5" />
    case 'IMPORT_FILES':
      return <ImportIcon className="w-3.5 h-3.5" />
    case 'GENERATE_PREVIEW':
      return <ImageIcon className="w-3.5 h-3.5" />
    case 'SYNC_IMPORT_SOURCE':
      return <SyncIcon className="w-3.5 h-3.5" />
    default:
      return <ProcessIcon className="w-3.5 h-3.5" />
  }
}

interface ActiveJobItemProps {
  job: QueueItem
  compact?: boolean
}

function ActiveJobItem({ job, compact = false }: ActiveJobItemProps) {
  const name = getJobDisplayName(job)
  const isRunning = job.status === 'RUNNING'
  const progress = job.progress ?? 0

  if (compact) {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className={isRunning ? 'text-accent-primary' : 'text-text-muted'}>
            {getJobTypeIcon(job.job_type)}
          </span>
          <span className="text-sm text-text-secondary truncate flex-1" title={name}>
            {name}
          </span>
          {isRunning && (
            <span className="text-xs text-text-muted">{Math.round(progress)}%</span>
          )}
        </div>
        {isRunning && <ProgressBar progress={progress} />}
      </div>
    )
  }

  return (
    <div className="space-y-1.5 py-1.5">
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 ${isRunning ? 'text-accent-primary' : 'text-text-muted'}`}>
          {getJobTypeIcon(job.job_type)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-primary truncate" title={name}>
              {name}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span>{getJobTypeLabel(job.job_type)}</span>
            {isRunning && job.progress_message && (
              <>
                <span>•</span>
                <span className="truncate">{job.progress_message}</span>
              </>
            )}
            {!isRunning && <span className="text-text-muted/70">Queued</span>}
          </div>
        </div>
        {isRunning && (
          <span className="text-xs text-accent-primary font-medium">{Math.round(progress)}%</span>
        )}
      </div>
      {isRunning && <ProgressBar progress={progress} />}
    </div>
  )
}

function SummaryView({ jobs }: { jobs: QueueItem[] }) {
  const runningJobs = jobs.filter((j) => j.status === 'RUNNING')
  const queuedCount = jobs.filter((j) => j.status === 'QUEUED').length

  if (runningJobs.length === 0 && queuedCount === 0) {
    return null
  }

  // Show first 2 running jobs in compact view
  const visibleJobs = runningJobs.slice(0, 2)
  const remainingRunning = runningJobs.length - visibleJobs.length

  return (
    <div className="px-3 py-2 space-y-2">
      {visibleJobs.map((job) => (
        <ActiveJobItem key={job.id} job={job} compact />
      ))}

      {remainingRunning > 0 && (
        <div className="text-xs text-text-muted pl-5">
          +{remainingRunning} more running
        </div>
      )}

      {queuedCount > 0 && visibleJobs.length > 0 && (
        <div className="text-xs text-text-muted pl-5">
          {queuedCount} queued
        </div>
      )}
    </div>
  )
}

function DetailedView({ jobs }: { jobs: QueueItem[] }) {
  const runningJobs = jobs.filter((j) => j.status === 'RUNNING')
  const queuedJobs = jobs.filter((j) => j.status === 'QUEUED')

  if (jobs.length === 0) {
    return (
      <div className="px-3 py-3">
        <div className="flex items-center gap-2 text-text-muted">
          <CheckIcon className="w-4 h-4 text-accent-success" />
          <span className="text-sm">All systems idle</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-3 py-2 space-y-1">
      {/* Running jobs first */}
      {runningJobs.length > 0 && (
        <div className="space-y-0.5">
          {runningJobs.map((job) => (
            <ActiveJobItem key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* Separator between running and queued */}
      {runningJobs.length > 0 && queuedJobs.length > 0 && (
        <div className="border-t border-bg-tertiary my-2" />
      )}

      {/* Queued jobs */}
      {queuedJobs.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-xs text-text-muted uppercase tracking-wider py-1">
            Queued ({queuedJobs.length})
          </div>
          {queuedJobs.slice(0, 5).map((job) => (
            <ActiveJobItem key={job.id} job={job} />
          ))}
          {queuedJobs.length > 5 && (
            <div className="text-xs text-text-muted py-1">
              +{queuedJobs.length - 5} more queued
            </div>
          )}
        </div>
      )}

      {/* Link to full queue */}
      <div className="pt-2 border-t border-bg-tertiary">
        <Link
          to="/queue"
          className="text-xs text-accent-primary hover:text-accent-primary/80 transition-colors"
        >
          View all activity →
        </Link>
      </div>
    </div>
  )
}

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="h-1 bg-bg-tertiary rounded-full overflow-hidden">
      <div
        className="h-full bg-accent-primary rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  )
}

function PulsingDot({ className }: { className?: string }) {
  return (
    <span className={`relative flex h-2.5 w-2.5 ${className}`}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-current" />
    </span>
  )
}

function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-sm">
        <WarningIcon className="w-4 h-4 text-accent-warning" />
        <span className="text-text-muted">Status unavailable</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs text-accent-primary hover:text-accent-primary/80"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  )
}

export function ActivityStatus() {
  const { data, isError, refetch } = useQueue({ status: 'RUNNING,QUEUED', page_size: 50 })
  const [isExpanded, setIsExpanded] = useState(getInitialExpanded)

  // Persist expanded state
  useEffect(() => {
    try {
      localStorage.setItem(EXPANDED_KEY, String(isExpanded))
    } catch {
      // Ignore localStorage errors
    }
  }, [isExpanded])

  const jobs = data?.items ?? []
  const hasActivity = jobs.length > 0
  const runningCount = jobs.filter((j) => j.status === 'RUNNING').length
  const queuedCount = jobs.filter((j) => j.status === 'QUEUED').length

  return (
    <div className="border-t border-bg-tertiary">
      {/* Header - clickable to toggle */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-bg-tertiary/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {hasActivity ? (
            <PulsingDot className="text-accent-primary" />
          ) : isError ? (
            <WarningIcon className="w-4 h-4 text-accent-warning" />
          ) : (
            <CheckIcon className="w-4 h-4 text-accent-success" />
          )}
          <span className="text-sm font-medium text-text-secondary">
            {hasActivity ? 'Active' : isError ? 'Status' : 'Idle'}
          </span>
          {hasActivity && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent-primary/20 text-accent-primary">
              {runningCount > 0 ? runningCount : queuedCount}
            </span>
          )}
        </div>
        <ChevronIcon className={`w-4 h-4 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-bg-tertiary">
          {isError ? (
            <ErrorState onRetry={() => refetch()} />
          ) : (
            <DetailedView jobs={jobs} />
          )}
        </div>
      )}

      {/* Summary when collapsed and has activity */}
      {!isExpanded && !isError && hasActivity && (
        <SummaryView jobs={jobs} />
      )}
    </div>
  )
}

// Icon Components

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
      />
    </svg>
  )
}

function ArchiveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
      />
    </svg>
  )
}

function ImportIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  )
}

function ImageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  )
}

function SyncIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  )
}

function ProcessIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  )
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  )
}
