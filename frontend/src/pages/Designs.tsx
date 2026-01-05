import { useState, useCallback } from 'react'
import { useDesigns, useMergeDesigns, useBulkDeleteDesigns } from '@/hooks/useDesigns'
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
import type { SortField, SortOrder, DesignListItem } from '@/types/design'

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
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showMergeModal, setShowMergeModal] = useState(false)
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false)
  const [bulkDeleteWithFiles, setBulkDeleteWithFiles] = useState(false)

  // Page size based on view
  const pageSize = view === 'grid' ? 24 : 20

  // Get filters from URL params
  const { filters, setFilters, removeFilter, clearFilters, setPage } = useDesignFilters(pageSize)

  // Merge mutation
  const mergeMutation = useMergeDesigns()
  const bulkDeleteMutation = useBulkDeleteDesigns()

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

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  // Get selected designs from current data
  const selectedDesigns = data?.items.filter((d) => selectedIds.has(d.id)) || []

  return (
    <div className="flex h-full -m-6">
      {/* Filter Sidebar */}
      <FilterSidebar
        filters={filters}
        onChange={setFilters}
        onClearAll={clearFilters}
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
                <DesignGrid
                  designs={data.items}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelection}
                />
              ) : (
                <DesignList
                  designs={data.items}
                  sortBy={filters.sort_by}
                  sortOrder={filters.sort_order}
                  onSort={handleColumnSort}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelection}
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

        {/* Selection Action Bar */}
        {selectedIds.size > 0 && (
          <div className="sticky bottom-0 bg-bg-secondary border-t border-bg-tertiary p-4 flex items-center justify-between">
            <span className="text-sm text-text-secondary">
              {selectedIds.size} design{selectedIds.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex gap-2">
              <button
                onClick={clearSelection}
                className="px-3 py-1.5 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
              >
                Clear Selection
              </button>
              <button
                onClick={() => setShowBulkDeleteModal(true)}
                className="px-3 py-1.5 text-sm rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors"
              >
                Delete Selected
              </button>
              <button
                onClick={() => setShowMergeModal(true)}
                disabled={selectedIds.size < 2}
                className="px-3 py-1.5 text-sm rounded bg-accent-primary text-white hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Merge Selected
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Merge Modal */}
      {showMergeModal && selectedDesigns.length >= 2 && (
        <MergeModal
          designs={selectedDesigns}
          onClose={() => setShowMergeModal(false)}
          onMerge={async (targetId) => {
            const sourceIds = Array.from(selectedIds).filter((id) => id !== targetId)
            await mergeMutation.mutateAsync({ targetId, sourceDesignIds: sourceIds })
            clearSelection()
            setShowMergeModal(false)
          }}
          isPending={mergeMutation.isPending}
        />
      )}

      {/* Bulk Delete Confirmation Modal */}
      {showBulkDeleteModal && (
        <BulkDeleteModal
          count={selectedIds.size}
          deleteFiles={bulkDeleteWithFiles}
          onDeleteFilesChange={setBulkDeleteWithFiles}
          onClose={() => {
            setShowBulkDeleteModal(false)
            setBulkDeleteWithFiles(false)
          }}
          onConfirm={async () => {
            await bulkDeleteMutation.mutateAsync({
              designIds: Array.from(selectedIds),
              deleteFiles: bulkDeleteWithFiles,
            })
            clearSelection()
            setShowBulkDeleteModal(false)
            setBulkDeleteWithFiles(false)
          }}
          isPending={bulkDeleteMutation.isPending}
        />
      )}
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

interface MergeModalProps {
  designs: DesignListItem[]
  onClose: () => void
  onMerge: (targetId: string) => Promise<void>
  isPending: boolean
}

function MergeModal({ designs, onClose, onMerge, isPending }: MergeModalProps) {
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleMerge = async () => {
    if (!selectedTargetId) return
    setError(null)
    try {
      await onMerge(selectedTargetId)
    } catch (err) {
      setError((err as Error).message || 'Failed to merge designs')
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-lg bg-bg-primary rounded-lg shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-bg-tertiary">
            <div>
              <h2 className="text-lg font-medium text-text-primary">
                Merge Designs
              </h2>
              <p className="text-sm text-text-muted mt-0.5">
                Select which design should be the primary (target)
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
            <p className="text-sm text-text-secondary">
              The selected design will become the primary. All other designs will be merged into it and deleted.
            </p>

            <div className="space-y-2">
              {designs.map((design) => (
                <label
                  key={design.id}
                  className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedTargetId === design.id
                      ? 'bg-accent-primary/20 border-accent-primary'
                      : 'bg-bg-secondary hover:bg-bg-tertiary'
                  }`}
                >
                  <input
                    type="radio"
                    name="targetDesign"
                    value={design.id}
                    checked={selectedTargetId === design.id}
                    onChange={() => setSelectedTargetId(design.id)}
                    className="text-accent-primary focus:ring-accent-primary"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {design.canonical_title}
                    </p>
                    <p className="text-xs text-text-muted truncate">
                      {design.canonical_designer} {design.channel && `- ${design.channel.title}`}
                    </p>
                  </div>
                  {selectedTargetId === design.id && (
                    <span className="text-xs px-2 py-0.5 rounded bg-accent-primary text-white">
                      Primary
                    </span>
                  )}
                </label>
              ))}
            </div>

            {error && (
              <div className="p-3 bg-accent-danger/20 rounded-lg">
                <p className="text-sm text-accent-danger">{error}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-bg-tertiary">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleMerge}
              disabled={!selectedTargetId || isPending}
              className="px-4 py-2 text-sm rounded bg-accent-primary text-white hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? 'Merging...' : `Merge ${designs.length} Designs`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function CloseIcon() {
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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

// Bulk Delete Modal
interface BulkDeleteModalProps {
  count: number
  deleteFiles: boolean
  onDeleteFilesChange: (value: boolean) => void
  onClose: () => void
  onConfirm: () => Promise<void>
  isPending: boolean
}

function BulkDeleteModal({
  count,
  deleteFiles,
  onDeleteFilesChange,
  onClose,
  onConfirm,
  isPending,
}: BulkDeleteModalProps) {
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    setError(null)
    try {
      await onConfirm()
    } catch (err) {
      setError((err as Error).message || 'Failed to delete designs')
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={isPending ? undefined : onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md bg-bg-primary rounded-lg shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-bg-tertiary">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-accent-danger/20 rounded-lg">
                <TrashIcon className="w-5 h-5 text-accent-danger" />
              </div>
              <h2 className="text-lg font-medium text-text-primary">
                Delete {count} Design{count !== 1 ? 's' : ''}
              </h2>
            </div>
            <button
              onClick={onClose}
              disabled={isPending}
              className="p-2 rounded text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors disabled:opacity-50"
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            <p className="text-text-secondary">
              Are you sure you want to delete {count} design{count !== 1 ? 's' : ''}?
              This action cannot be undone.
            </p>

            <div className="space-y-3 pt-2">
              <p className="text-sm text-text-muted">
                Choose what to delete:
              </p>
              <label className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary cursor-pointer hover:bg-bg-tertiary transition-colors">
                <input
                  type="radio"
                  name="bulkDeleteOption"
                  checked={!deleteFiles}
                  onChange={() => onDeleteFilesChange(false)}
                  className="mt-0.5 text-accent-primary focus:ring-accent-primary"
                />
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    Database only
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">
                    Remove from Printarr but keep files in library
                  </p>
                </div>
              </label>
              <label className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary cursor-pointer hover:bg-bg-tertiary transition-colors">
                <input
                  type="radio"
                  name="bulkDeleteOption"
                  checked={deleteFiles}
                  onChange={() => onDeleteFilesChange(true)}
                  className="mt-0.5 text-accent-danger focus:ring-accent-danger"
                />
                <div>
                  <p className="text-sm font-medium text-accent-danger">
                    Database + Files
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">
                    Remove from Printarr and delete all files from disk
                  </p>
                </div>
              </label>
            </div>

            {error && (
              <div className="p-3 bg-accent-danger/20 rounded-lg">
                <p className="text-sm text-accent-danger">{error}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-bg-tertiary">
            <button
              onClick={onClose}
              disabled={isPending}
              className="px-4 py-2 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isPending}
              className="px-4 py-2 text-sm rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
            >
              {isPending ? 'Deleting...' : `Delete ${count} Design${count !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
