import { useState, useRef, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useActivity, useRemoveActivity, useClearFailedActivity } from '@/hooks/useQueue'
import { HistoryItem } from './HistoryItem'
import type { ActivityListParams, ActivityItem } from '@/types/queue'

type StatusFilter = 'all' | 'SUCCESS' | 'FAILED'
type JobTypeFilter = 'all' | 'DOWNLOAD_DESIGN' | 'EXTRACT_ARCHIVE' | 'IMPORT_FILES' | 'GENERATE_PREVIEW'
type DateFilter = 'all' | '24h' | '7d' | '30d'

// Estimated row height for history items (actual height varies)
const ESTIMATED_ITEM_HEIGHT = 140

export function HistoryView() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [jobTypeFilter, setJobTypeFilter] = useState<JobTypeFilter>('all')
  const [dateFilter, setDateFilter] = useState<DateFilter>('all')
  const [page, setPage] = useState(1)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [showClearFailedConfirm, setShowClearFailedConfirm] = useState(false)
  const parentRef = useRef<HTMLDivElement>(null)

  // Build query params
  const params: ActivityListParams = {
    page,
    page_size: 50,
  }

  if (statusFilter !== 'all') {
    params.status = statusFilter
  }

  if (jobTypeFilter !== 'all') {
    params.job_type = jobTypeFilter
  }

  const { data, isLoading, error } = useActivity(params)
  const removeActivity = useRemoveActivity()
  const clearFailed = useClearFailedActivity()

  // Handle clear all
  const handleClearAll = async () => {
    if (!data?.items) return

    try {
      // Remove each item
      for (const item of data.items) {
        await removeActivity.mutateAsync(item.id)
      }
      setShowClearConfirm(false)
    } catch (error) {
      console.error('Failed to clear history:', error)
    }
  }

  // DEC-042: Handle clear all failed
  const handleClearFailed = async () => {
    try {
      await clearFailed.mutateAsync()
      setShowClearFailedConfirm(false)
    } catch (error) {
      console.error('Failed to clear failed jobs:', error)
    }
  }

  if (isLoading) {
    return <HistoryViewSkeleton />
  }

  if (error) {
    return (
      <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
        <p className="text-accent-danger">
          Failed to load history: {(error as Error).message}
        </p>
      </div>
    )
  }

  const items = data?.items || []
  const isEmpty = items.length === 0
  const totalPages = data?.pages || 1

  // Filter by date on client side (API may not support date filtering)
  const filteredItems = items.filter((item) => {
    if (dateFilter === 'all') return true
    if (!item.completed_at) return false

    const completedDate = new Date(item.completed_at)
    const now = new Date()
    const diffMs = now.getTime() - completedDate.getTime()
    const diffHours = diffMs / (1000 * 60 * 60)

    switch (dateFilter) {
      case '24h':
        return diffHours <= 24
      case '7d':
        return diffHours <= 24 * 7
      case '30d':
        return diffHours <= 24 * 30
      default:
        return true
    }
  })

  // Count stats
  const successCount = items.filter(i => i.status === 'SUCCESS').length
  const failedCount = items.filter(i => i.status === 'FAILED').length

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-bg-secondary rounded-lg p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-muted">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as StatusFilter)
                setPage(1)
              }}
              className="text-sm px-3 py-1.5 rounded bg-bg-tertiary text-text-primary border-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="all">All ({items.length})</option>
              <option value="SUCCESS">Success ({successCount})</option>
              <option value="FAILED">Failed ({failedCount})</option>
            </select>
          </div>

          {/* Job type filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-muted">Type:</span>
            <select
              value={jobTypeFilter}
              onChange={(e) => {
                setJobTypeFilter(e.target.value as JobTypeFilter)
                setPage(1)
              }}
              className="text-sm px-3 py-1.5 rounded bg-bg-tertiary text-text-primary border-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="all">All Types</option>
              <option value="DOWNLOAD_DESIGN">Downloads</option>
              <option value="EXTRACT_ARCHIVE">Extractions</option>
              <option value="IMPORT_FILES">Imports</option>
              <option value="GENERATE_PREVIEW">Previews</option>
            </select>
          </div>

          {/* Date filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-muted">Date:</span>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as DateFilter)}
              className="text-sm px-3 py-1.5 rounded bg-bg-tertiary text-text-primary border-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="all">All Time</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>

          {/* Action buttons */}
          <div className="ml-auto flex items-center gap-2">
            {/* DEC-042: Clear All Failed button */}
            {failedCount > 0 && (
              <button
                onClick={() => setShowClearFailedConfirm(true)}
                className="text-sm px-3 py-1.5 rounded bg-accent-warning/20 text-accent-warning hover:bg-accent-warning/30 transition-colors"
              >
                Clear Failed ({failedCount})
              </button>
            )}
            {/* Clear all button */}
            {items.length > 0 && (
              <button
                onClick={() => setShowClearConfirm(true)}
                className="text-sm px-3 py-1.5 rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors"
              >
                Clear History
              </button>
            )}
          </div>
        </div>

        {/* DEC-042: Clear Failed confirmation */}
        {showClearFailedConfirm && (
          <div className="mt-4 p-3 bg-bg-tertiary rounded-lg">
            <p className="text-sm text-text-primary mb-3">
              Clear all {failedCount} failed job{failedCount !== 1 ? 's' : ''} from history? This cannot be undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleClearFailed}
                disabled={clearFailed.isPending}
                className="text-xs px-3 py-1.5 rounded bg-accent-warning text-white hover:bg-accent-warning/80 transition-colors disabled:opacity-50"
              >
                {clearFailed.isPending ? 'Clearing...' : 'Yes, Clear Failed'}
              </button>
              <button
                onClick={() => setShowClearFailedConfirm(false)}
                className="text-xs px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Clear confirmation */}
        {showClearConfirm && (
          <div className="mt-4 p-3 bg-bg-tertiary rounded-lg">
            <p className="text-sm text-text-primary mb-3">
              Clear all history? This cannot be undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleClearAll}
                disabled={removeActivity.isPending}
                className="text-xs px-3 py-1.5 rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
              >
                {removeActivity.isPending ? 'Clearing...' : 'Yes, Clear All'}
              </button>
              <button
                onClick={() => setShowClearConfirm(false)}
                className="text-xs px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Empty state */}
      {isEmpty && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <EmptyHistoryIcon className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No history yet
          </h3>
          <p className="text-text-secondary">
            Completed and failed downloads will appear here.
          </p>
        </div>
      )}

      {/* Virtualized History list */}
      {filteredItems.length > 0 && (
        <VirtualizedHistoryList items={filteredItems} parentRef={parentRef} />
      )}

      {/* No results after filtering */}
      {items.length > 0 && filteredItems.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <p className="text-text-secondary">
            No items match the current filters.
          </p>
          <button
            onClick={() => {
              setStatusFilter('all')
              setJobTypeFilter('all')
              setDateFilter('all')
            }}
            className="mt-4 text-sm text-accent-primary hover:underline"
          >
            Clear filters
          </button>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-text-muted">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

// Virtualized history list component
interface VirtualizedHistoryListProps {
  items: ActivityItem[]
  parentRef: React.RefObject<HTMLDivElement | null>
}

function VirtualizedHistoryList({ items, parentRef }: VirtualizedHistoryListProps) {
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => ESTIMATED_ITEM_HEIGHT, []),
    overscan: 5, // Render extra items for smooth scrolling
    gap: 12, // space-y-3 = 12px gap
  })

  return (
    <div
      ref={parentRef}
      className="overflow-auto h-[calc(100vh-380px)]"
      style={{ contain: 'strict' }}
    >
      <div
        style={{
          height: virtualizer.getTotalSize(),
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index]
          return (
            <div
              key={item.id}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <HistoryItem item={item} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Empty history icon
function EmptyHistoryIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

// Skeleton loader
function HistoryViewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Filters skeleton */}
      <div className="bg-bg-secondary rounded-lg p-4">
        <div className="flex flex-wrap items-center gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="h-4 bg-bg-tertiary rounded w-12" />
              <div className="h-8 bg-bg-tertiary rounded w-32" />
            </div>
          ))}
        </div>
      </div>

      {/* Items skeleton */}
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-bg-secondary rounded-lg p-4">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-bg-tertiary rounded-lg" />
              <div className="flex-1 space-y-2">
                <div className="h-5 bg-bg-tertiary rounded w-2/3" />
                <div className="h-4 bg-bg-tertiary rounded w-1/2" />
                <div className="h-3 bg-bg-tertiary rounded w-1/4 mt-2" />
              </div>
              <div className="h-6 bg-bg-tertiary rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
