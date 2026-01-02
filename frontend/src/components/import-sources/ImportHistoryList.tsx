/**
 * Import history list component showing detected/imported designs from a source
 */
import { useState } from 'react'
import { useImportHistory } from '@/hooks/useImportSources'
import type { ImportRecordStatus } from '@/types/import-source'

interface ImportHistoryListProps {
  sourceId: string
  onDesignClick?: (designId: string) => void
}

export function ImportHistoryList({ sourceId, onDesignClick }: ImportHistoryListProps) {
  const [statusFilter, setStatusFilter] = useState<ImportRecordStatus | ''>('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading, error } = useImportHistory(sourceId, {
    status: statusFilter || undefined,
    page,
    page_size: pageSize,
  })

  const getStatusBadge = (status: ImportRecordStatus) => {
    const styles: Record<ImportRecordStatus, string> = {
      PENDING: 'bg-accent-warning/20 text-accent-warning',
      IMPORTING: 'bg-accent-primary/20 text-accent-primary',
      IMPORTED: 'bg-accent-success/20 text-accent-success',
      SKIPPED: 'bg-text-muted/20 text-text-muted',
      ERROR: 'bg-accent-danger/20 text-accent-danger',
    }
    const labels: Record<ImportRecordStatus, string> = {
      PENDING: 'Pending',
      IMPORTING: 'Importing',
      IMPORTED: 'Imported',
      SKIPPED: 'Skipped',
      ERROR: 'Error',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status]}`}>
        {labels[status]}
      </span>
    )
  }

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-bg-tertiary rounded-lg p-4 animate-pulse">
            <div className="h-4 w-3/4 bg-bg-secondary rounded mb-2" />
            <div className="h-3 w-1/2 bg-bg-secondary rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
        <p className="text-accent-danger">Failed to load import history</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ImportRecordStatus | '')
            setPage(1)
          }}
          className="bg-bg-tertiary text-text-primary rounded-lg px-3 py-2 text-sm border border-bg-tertiary focus:outline-none focus:ring-2 focus:ring-accent-primary"
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="IMPORTING">Importing</option>
          <option value="IMPORTED">Imported</option>
          <option value="SKIPPED">Skipped</option>
          <option value="ERROR">Error</option>
        </select>
        {data && (
          <span className="text-sm text-text-muted">
            {data.total} item{data.total !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* History list */}
      {data && data.items.length === 0 ? (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <HistoryIcon className="w-12 h-12 text-text-muted mx-auto mb-3" />
          <p className="text-text-secondary">No import history yet</p>
          <p className="text-sm text-text-muted mt-1">
            Designs will appear here after you sync this source
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {data?.items.map((item) => (
            <div
              key={item.id}
              className={`bg-bg-secondary rounded-lg p-4 ${
                item.design_id && onDesignClick ? 'cursor-pointer hover:bg-bg-tertiary transition-colors' : ''
              }`}
              onClick={() => item.design_id && onDesignClick?.(item.design_id)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {getStatusBadge(item.status)}
                    {item.detected_title && (
                      <span className="text-text-primary font-medium truncate">
                        {item.detected_title}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-text-muted truncate font-mono">{item.source_path}</p>
                  {item.error_message && (
                    <p className="text-sm text-accent-danger mt-1">{item.error_message}</p>
                  )}
                </div>
                <div className="text-right text-sm text-text-muted flex-shrink-0">
                  <p>Detected {formatRelativeTime(item.detected_at)}</p>
                  {item.imported_at && (
                    <p>Imported {formatRelativeTime(item.imported_at)}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 bg-bg-tertiary rounded text-sm text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-text-muted">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 bg-bg-tertiary rounded text-sm text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
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

function HistoryIcon({ className }: { className?: string }) {
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
