/**
 * Sync status badge component showing current sync state
 */
import type { ReactNode } from 'react'
import type { ImportSourceStatus } from '@/types/import-source'

interface SyncStatusBadgeProps {
  status: ImportSourceStatus
  lastSyncAt?: string | null
  lastError?: string | null
  compact?: boolean
}

export function SyncStatusBadge({
  status,
  lastSyncAt,
  lastError,
  compact = false,
}: SyncStatusBadgeProps) {
  const getStatusConfig = (status: ImportSourceStatus) => {
    const configs: Record<
      ImportSourceStatus,
      { icon: ReactNode; color: string; label: string; bgColor: string }
    > = {
      ACTIVE: {
        icon: <CheckIcon className="w-4 h-4" />,
        color: 'text-accent-success',
        bgColor: 'bg-accent-success/20',
        label: 'Active',
      },
      PAUSED: {
        icon: <PauseIcon className="w-4 h-4" />,
        color: 'text-text-muted',
        bgColor: 'bg-text-muted/20',
        label: 'Paused',
      },
      ERROR: {
        icon: <ErrorIcon className="w-4 h-4" />,
        color: 'text-accent-danger',
        bgColor: 'bg-accent-danger/20',
        label: 'Error',
      },
      PENDING: {
        icon: <ClockIcon className="w-4 h-4" />,
        color: 'text-accent-warning',
        bgColor: 'bg-accent-warning/20',
        label: 'Pending',
      },
      RATE_LIMITED: {
        icon: <ThrottleIcon className="w-4 h-4" />,
        color: 'text-amber-500',
        bgColor: 'bg-amber-500/20',
        label: 'Rate Limited',
      },
    }
    return configs[status]
  }

  const config = getStatusConfig(status)

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.bgColor} ${config.color}`}
        title={lastError || undefined}
      >
        {config.icon}
        <span>{config.label}</span>
      </span>
    )
  }

  return (
    <div className="space-y-1">
      <div className={`flex items-center gap-2 ${config.color}`}>
        {config.icon}
        <span className="text-sm font-medium">{config.label}</span>
      </div>
      {lastSyncAt && (
        <p className="text-xs text-text-muted">
          Last sync: {formatRelativeTime(lastSyncAt)}
        </p>
      )}
      {(status === 'ERROR' || status === 'RATE_LIMITED') && lastError && (
        <p className={`text-xs ${status === 'RATE_LIMITED' ? 'text-amber-500' : 'text-accent-danger'} truncate max-w-[200px]`} title={lastError}>
          {lastError}
        </p>
      )}
    </div>
  )
}

// =============================================================================
// Utilities
// =============================================================================

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

// =============================================================================
// Icons
// =============================================================================

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function PauseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function ErrorIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function ThrottleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  )
}
