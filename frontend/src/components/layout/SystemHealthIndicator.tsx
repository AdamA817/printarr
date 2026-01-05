/**
 * SystemHealthIndicator - Sidebar health status indicator (DEC-042)
 *
 * Shows system health status with subsystem details:
 * - Database: connectivity and latency
 * - Telegram: connection and auth status
 * - Workers: job queue status
 * - Storage: disk usage
 * - Rate Limiter: throttling status
 */
import { useState, useEffect } from 'react'
import { useDetailedHealth } from '@/hooks/useHealth'
import type { SubsystemStatus, DetailedHealthResponse } from '@/types/health'

// Persist expanded state in localStorage
const EXPANDED_KEY = 'printarr:health-expanded'

function getInitialExpanded(): boolean {
  try {
    const stored = localStorage.getItem(EXPANDED_KEY)
    return stored === 'true'
  } catch {
    return false
  }
}

// Status background colors for indicators
const statusBgColors: Record<SubsystemStatus, string> = {
  healthy: 'bg-accent-success',
  degraded: 'bg-accent-warning',
  unhealthy: 'bg-accent-danger',
}

interface SubsystemRowProps {
  label: string
  status: SubsystemStatus
  detail?: string
}

function SubsystemRow({ label, status, detail }: SubsystemRowProps) {
  return (
    <div className="flex items-center justify-between py-1">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${statusBgColors[status]}`} />
        <span className="text-xs text-text-secondary">{label}</span>
      </div>
      {detail && (
        <span className="text-xs text-text-muted">{detail}</span>
      )}
    </div>
  )
}

function formatBytes(gb: number): string {
  if (gb < 1) return `${(gb * 1024).toFixed(0)} MB`
  return `${gb.toFixed(1)} GB`
}

function DetailedView({ data }: { data: DetailedHealthResponse }) {
  const { subsystems } = data

  return (
    <div className="px-3 py-2 space-y-2">
      <SubsystemRow
        label="Database"
        status={subsystems.database.status}
        detail={subsystems.database.latency_ms !== null ? `${subsystems.database.latency_ms.toFixed(0)}ms` : undefined}
      />
      <SubsystemRow
        label="Telegram"
        status={subsystems.telegram.status}
        detail={subsystems.telegram.authenticated ? 'Connected' : subsystems.telegram.connected ? 'Not Auth' : 'Offline'}
      />
      <SubsystemRow
        label="Workers"
        status={subsystems.workers.status}
        detail={`${subsystems.workers.jobs_running} running, ${subsystems.workers.jobs_queued} queued`}
      />
      <SubsystemRow
        label="Storage"
        status={subsystems.storage.status}
        detail={`${formatBytes(subsystems.storage.library_free_gb)} free`}
      />
      <SubsystemRow
        label="Rate Limiter"
        status={subsystems.rate_limiter.status}
        detail={subsystems.rate_limiter.channels_in_backoff > 0 ? `${subsystems.rate_limiter.channels_in_backoff} throttled` : undefined}
      />

      {/* Recent errors */}
      {data.errors.length > 0 && (
        <div className="pt-2 border-t border-bg-tertiary">
          <div className="text-xs text-text-muted mb-1">Recent Errors</div>
          <div className="space-y-1">
            {data.errors.slice(0, 3).map((error) => (
              <div key={error.job_id} className="text-xs text-accent-danger truncate" title={error.error}>
                {error.error.slice(0, 50)}...
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Version */}
      <div className="pt-2 border-t border-bg-tertiary text-xs text-text-muted">
        Version {data.version}
      </div>
    </div>
  )
}

export function SystemHealthIndicator() {
  const { data, isError, refetch } = useDetailedHealth()
  const [isExpanded, setIsExpanded] = useState(getInitialExpanded)

  // Persist expanded state
  useEffect(() => {
    try {
      localStorage.setItem(EXPANDED_KEY, String(isExpanded))
    } catch {
      // Ignore localStorage errors
    }
  }, [isExpanded])

  // Determine overall status
  const overallStatus = data?.overall || 'healthy'
  const hasIssues = overallStatus !== 'healthy'

  return (
    <div className="border-t border-bg-tertiary">
      {/* Header - clickable to toggle */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-bg-tertiary/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${statusBgColors[overallStatus]}`} />
          <span className="text-sm font-medium text-text-secondary">
            System
          </span>
          {hasIssues && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${overallStatus === 'degraded' ? 'bg-accent-warning/20 text-accent-warning' : 'bg-accent-danger/20 text-accent-danger'}`}>
              {overallStatus === 'degraded' ? 'Degraded' : 'Unhealthy'}
            </span>
          )}
        </div>
        <ChevronIcon className={`w-4 h-4 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-bg-tertiary">
          {isError ? (
            <div className="px-3 py-2">
              <div className="flex items-center gap-2 text-sm">
                <WarningIcon className="w-4 h-4 text-accent-warning" />
                <span className="text-text-muted">Status unavailable</span>
                <button
                  onClick={() => refetch()}
                  className="text-xs text-accent-primary hover:text-accent-primary/80"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : data ? (
            <DetailedView data={data} />
          ) : (
            <div className="px-3 py-2 text-sm text-text-muted">Loading...</div>
          )}
        </div>
      )}
    </div>
  )
}

// Icon Components

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
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
