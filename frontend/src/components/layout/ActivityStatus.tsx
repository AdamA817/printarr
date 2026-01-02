/**
 * ActivityStatus - Sidebar activity indicator (v0.7)
 *
 * Radarr-style status indicator showing background processes:
 * - Syncing (channel sync/backfill)
 * - Downloads (active/queued)
 * - Images (Telegram, renders)
 * - Analysis (extraction, import, 3MF)
 */
import { useState, useEffect } from 'react'
import { useSystemActivity } from '@/hooks/useSystemActivity'
import type { SystemActivityResponse } from '@/types/system'

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

interface ActivityCategoryProps {
  icon: React.ReactNode
  label: string
  items: { label: string; count: number }[]
  isActive: boolean
}

function ActivityCategory({ icon, label, items, isActive }: ActivityCategoryProps) {
  const hasActivity = items.some((item) => item.count > 0)

  if (!hasActivity) return null

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <span className={isActive ? 'text-accent-primary' : 'text-text-muted'}>{icon}</span>
        <span className="font-medium">{label}</span>
      </div>
      <div className="ml-5 space-y-0.5">
        {items.map(
          (item) =>
            item.count > 0 && (
              <div key={item.label} className="text-xs text-text-muted flex justify-between">
                <span>{item.label}</span>
                <span className="text-text-secondary">{item.count}</span>
              </div>
            )
        )}
      </div>
    </div>
  )
}

function SummaryView({ data }: { data: SystemActivityResponse }) {
  const { sync, downloads, images, analysis, summary } = data

  // Calculate what's active for summary display
  const syncCount = sync.channels_syncing + sync.backfills_running
  const imageCount = images.telegram_downloading + images.previews_generating
  const analysisCount =
    analysis.archives_extracting + analysis.importing_to_library + analysis.analyzing_3mf

  // Determine what to show in summary
  const showSync = syncCount > 0
  const showDownloads = downloads.active > 0 || downloads.queued > 0
  const showImages = imageCount > 0
  const showAnalysis = analysisCount > 0

  if (summary.is_idle) {
    return (
      <div className="flex items-center gap-2 px-3 py-2">
        <CheckIcon className="w-4 h-4 text-accent-success" />
        <span className="text-sm text-text-muted">Idle</span>
      </div>
    )
  }

  return (
    <div className="px-3 py-2 space-y-1.5">
      {showSync && (
        <div className="flex items-center gap-2 text-sm">
          <PulsingDot className="text-accent-primary" />
          <span className="text-text-secondary">
            Syncing {syncCount} channel{syncCount !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {showDownloads && (
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm">
            <DownloadIcon className="w-3.5 h-3.5 text-accent-primary" />
            <span className="text-text-secondary">
              {downloads.active}/{downloads.active + downloads.queued} downloads
            </span>
          </div>
          {downloads.active > 0 && <ProgressBar progress={downloads.active / (downloads.active + downloads.queued) * 100} />}
        </div>
      )}

      {showImages && (
        <div className="flex items-center gap-2 text-sm">
          <ImageIcon className="w-3.5 h-3.5 text-purple-400" />
          <span className="text-text-secondary">
            {imageCount} image{imageCount !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {showAnalysis && (
        <div className="flex items-center gap-2 text-sm">
          <AnalysisIcon className="w-3.5 h-3.5 text-orange-400" />
          <span className="text-text-secondary">
            {analysisCount} analyzing
          </span>
        </div>
      )}
    </div>
  )
}

function DetailedView({ data }: { data: SystemActivityResponse }) {
  const { sync, downloads, images, analysis } = data

  return (
    <div className="px-3 py-3 space-y-4">
      <ActivityCategory
        icon={<SyncIcon className="w-4 h-4" />}
        label="Sync"
        isActive={sync.channels_syncing > 0 || sync.backfills_running > 0}
        items={[
          { label: 'Channels', count: sync.channels_syncing },
          { label: 'Backfill', count: sync.backfills_running },
        ]}
      />

      <ActivityCategory
        icon={<DownloadIcon className="w-4 h-4" />}
        label="Downloads"
        isActive={downloads.active > 0}
        items={[
          { label: 'Active', count: downloads.active },
          { label: 'Queued', count: downloads.queued },
        ]}
      />

      {(downloads.active > 0 || downloads.queued > 0) && (
        <div className="ml-5">
          <ProgressBar progress={downloads.active / Math.max(downloads.active + downloads.queued, 1) * 100} />
        </div>
      )}

      <ActivityCategory
        icon={<ImageIcon className="w-4 h-4" />}
        label="Images"
        isActive={images.telegram_downloading > 0 || images.previews_generating > 0}
        items={[
          { label: 'Telegram', count: images.telegram_downloading },
          { label: 'Renders', count: images.previews_generating },
        ]}
      />

      <ActivityCategory
        icon={<AnalysisIcon className="w-4 h-4" />}
        label="Analysis"
        isActive={
          analysis.archives_extracting > 0 ||
          analysis.importing_to_library > 0 ||
          analysis.analyzing_3mf > 0
        }
        items={[
          { label: 'Extracting', count: analysis.archives_extracting },
          { label: 'Importing', count: analysis.importing_to_library },
          { label: '3MF Analysis', count: analysis.analyzing_3mf },
        ]}
      />

      {/* Show idle message if nothing active */}
      {data.summary.is_idle && (
        <div className="flex items-center gap-2 text-text-muted">
          <CheckIcon className="w-4 h-4 text-accent-success" />
          <span className="text-sm">All systems idle</span>
        </div>
      )}
    </div>
  )
}

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
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
  const { data, isError, refetch } = useSystemActivity()
  const [isExpanded, setIsExpanded] = useState(getInitialExpanded)

  // Persist expanded state
  useEffect(() => {
    try {
      localStorage.setItem(EXPANDED_KEY, String(isExpanded))
    } catch {
      // Ignore localStorage errors
    }
  }, [isExpanded])

  const hasActivity = data && !data.summary.is_idle

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
          {data && !data.summary.is_idle && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent-primary/20 text-accent-primary">
              {data.summary.total_active + data.summary.total_queued}
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
          ) : data ? (
            <DetailedView data={data} />
          ) : (
            <div className="px-3 py-2 text-sm text-text-muted">Loading...</div>
          )}
        </div>
      )}

      {/* Summary when collapsed and has activity */}
      {!isExpanded && !isError && data && !data.summary.is_idle && (
        <SummaryView data={data} />
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

function AnalysisIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
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
