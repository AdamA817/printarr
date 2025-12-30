import { useState, useMemo } from 'react'
import { useDesigns } from '@/hooks/useDesigns'
import {
  DesignGrid,
  DesignGridSkeleton,
  DesignList,
  DesignListSkeleton,
  ViewToggle,
  type ViewMode,
} from '@/components/designs'
import type { DesignListParams } from '@/types/design'

const VIEW_STORAGE_KEY = 'printarr-designs-view'

function getStoredView(): ViewMode {
  try {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY)
    if (stored === 'grid' || stored === 'list') {
      return stored
    }
  } catch {
    // localStorage not available
  }
  return 'grid' // Default to grid view
}

function setStoredView(view: ViewMode) {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, view)
  } catch {
    // localStorage not available
  }
}

export function Designs() {
  const [view, setView] = useState<ViewMode>(getStoredView)
  const [page, setPage] = useState(1)

  // Compute page_size based on view - grid shows more items
  const pageSize = view === 'grid' ? 24 : 20

  // Build params from state
  const params: DesignListParams = useMemo(
    () => ({ page, page_size: pageSize }),
    [page, pageSize]
  )

  const { data, isLoading, error } = useDesigns(params)

  const handleViewChange = (newView: ViewMode) => {
    setView(newView)
    setStoredView(newView)
    setPage(1) // Reset to first page when view changes
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Designs</h1>
          {data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} design{data.total !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <ViewToggle view={view} onChange={handleViewChange} />
      </div>

      {/* Loading state */}
      {isLoading && (
        view === 'grid' ? <DesignGridSkeleton /> : <DesignListSkeleton />
      )}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load designs: {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">📐</div>
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No designs yet
          </h3>
          <p className="text-text-secondary mb-4">
            Designs will appear here after you run a backfill on a channel with 3D models.
          </p>
        </div>
      )}

      {/* Content */}
      {data && data.items.length > 0 && (
        <>
          {view === 'grid' ? (
            <DesignGrid designs={data.items} />
          ) : (
            <DesignList designs={data.items} />
          )}

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-between py-4">
              <p className="text-sm text-text-secondary">
                Page {data.page} of {data.pages} ({data.total} total)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handlePageChange(data.page - 1)}
                  disabled={data.page <= 1}
                  className="px-3 py-1 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => handlePageChange(data.page + 1)}
                  disabled={data.page >= data.pages}
                  className="px-3 py-1 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
