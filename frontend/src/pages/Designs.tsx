import { useState, useCallback } from 'react'
import { useDesigns } from '@/hooks/useDesigns'
import { useDesignFilters } from '@/hooks/useDesignFilters'
import { useChannels } from '@/hooks/useChannels'
import {
  DesignGrid,
  DesignGridSkeleton,
  DesignList,
  DesignListSkeleton,
  ViewToggle,
  FilterSidebar,
  ActiveFilters,
  SearchBox,
  SortControls,
  type ViewMode,
} from '@/components/designs'
import type { SortField, SortOrder } from '@/types/design'

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
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Page size based on view
  const pageSize = view === 'grid' ? 24 : 20

  // Get filters from URL params
  const { filters, setFilters, removeFilter, setPage } = useDesignFilters(pageSize)

  // Merge page_size with filters
  const effectiveFilters = { ...filters, page_size: pageSize }

  // Fetch designs with current filters
  const { data, isLoading, error } = useDesigns(effectiveFilters)

  // Fetch channels for filter dropdown and active filter display
  const { data: channelsData } = useChannels({ page_size: 100 })

  // Get channel name for active filter display
  const selectedChannelName = filters.channel_id && channelsData?.items
    ? channelsData.items.find(c => c.id === filters.channel_id)?.title
    : undefined

  const handleViewChange = useCallback((newView: ViewMode) => {
    setView(newView)
    setStoredView(newView)
    setPage(1) // Reset to first page when view changes
  }, [setPage])

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage)
  }, [setPage])

  const handleSearchChange = useCallback((q: string) => {
    setFilters({ q: q || undefined, page: 1 })
  }, [setFilters])

  const handleSortChange = useCallback((sortBy: SortField, sortOrder: SortOrder) => {
    setFilters({ sort_by: sortBy, sort_order: sortOrder, page: 1 })
  }, [setFilters])

  const handleColumnSort = useCallback((field: SortField) => {
    // Toggle direction if same field, otherwise use default direction
    if (field === filters.sort_by) {
      const newOrder = filters.sort_order === 'ASC' ? 'DESC' : 'ASC'
      setFilters({ sort_order: newOrder, page: 1 })
    } else {
      const defaultOrder = field === 'created_at' || field === 'total_size_bytes' ? 'DESC' : 'ASC'
      setFilters({ sort_by: field, sort_order: defaultOrder, page: 1 })
    }
  }, [filters.sort_by, filters.sort_order, setFilters])

  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prev => !prev)
  }, [])

  const closeSidebar = useCallback(() => {
    setSidebarOpen(false)
  }, [])

  return (
    <div className="flex h-full -m-6">
      {/* Filter Sidebar */}
      <FilterSidebar
        filters={filters}
        onChange={setFilters}
        isOpen={sidebarOpen}
        onClose={closeSidebar}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Header Row 1: Title and View Toggle */}
          <div className="flex justify-between items-center gap-4">
            <div className="flex items-center gap-4">
              {/* Mobile filter toggle */}
              <button
                onClick={toggleSidebar}
                className="lg:hidden p-2 rounded bg-bg-secondary text-text-secondary hover:text-text-primary"
                aria-label="Toggle filters"
              >
                <FilterIcon />
              </button>
              <div>
                <h1 className="text-xl font-bold text-text-primary">Designs</h1>
                {data && (
                  <p className="text-sm text-text-secondary mt-1">
                    {data.total} design{data.total !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
            </div>
            <ViewToggle view={view} onChange={handleViewChange} />
          </div>

          {/* Header Row 2: Search and Sort */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 max-w-md">
              <SearchBox
                value={filters.q || ''}
                onChange={handleSearchChange}
                placeholder="Search designs..."
              />
            </div>
            <SortControls
              sortBy={filters.sort_by || 'created_at'}
              sortOrder={filters.sort_order || 'DESC'}
              onSortChange={handleSortChange}
            />
          </div>

          {/* Active Filters Pills */}
          <ActiveFilters
            filters={filters}
            channelName={selectedChannelName}
            onRemove={removeFilter}
          />

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
                {filters.status || filters.channel_id || filters.file_type || filters.q
                  ? 'No designs match your filters'
                  : 'No designs yet'}
              </h3>
              <p className="text-text-secondary mb-4">
                {filters.status || filters.channel_id || filters.file_type || filters.q
                  ? 'Try adjusting your filters to see more results.'
                  : 'Designs will appear here after you run a backfill on a channel with 3D models.'}
              </p>
            </div>
          )}

          {/* Content */}
          {data && data.items.length > 0 && (
            <>
              {view === 'grid' ? (
                <DesignGrid designs={data.items} />
              ) : (
                <DesignList
                  designs={data.items}
                  sortBy={filters.sort_by}
                  sortOrder={filters.sort_order}
                  onSort={handleColumnSort}
                />
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
      </div>
    </div>
  )
}

function FilterIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  )
}
