import { useState, useCallback, useRef } from 'react'
import { useMergeDesigns, useBulkDeleteDesigns } from '@/hooks/useDesigns'
import { useDesignFilters } from '@/hooks/useDesignFilters'
import {
  useInfiniteDesigns,
  flattenInfiniteDesigns,
  getInfiniteDesignsTotal,
} from '@/hooks/useInfiniteDesigns'
import { useSavedFilters } from '@/hooks/useSavedFilters'
import {
  DesignToolbar,
  CustomFilterModal,
  InfiniteDesignGrid,
  ScrollToTopButton,
  type ViewMode,
} from '@/components/designs'
import type { SortField, SortOrder, DesignListItem, DesignListParams } from '@/types/design'

const VIEW_STORAGE_KEY = 'printarr-designs-view'
const ACTIVE_FILTER_KEY = 'printarr-active-filter'

function getStoredView(): ViewMode {
  try {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY)
    if (stored === 'grid' || stored === 'list') {
      return stored
    }
  } catch {
    // localStorage not available
  }
  return 'grid'
}

function setStoredView(view: ViewMode) {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, view)
  } catch {
    // localStorage not available
  }
}

function getStoredActiveFilter(): string {
  try {
    return localStorage.getItem(ACTIVE_FILTER_KEY) || 'all'
  } catch {
    return 'all'
  }
}

function setStoredActiveFilter(id: string) {
  try {
    localStorage.setItem(ACTIVE_FILTER_KEY, id)
  } catch {
    // localStorage not available
  }
}

export function Designs() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<ViewMode>(getStoredView)
  const [activeFilterId, setActiveFilterId] = useState<string | null>(getStoredActiveFilter)
  const [showCustomFilterModal, setShowCustomFilterModal] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showMergeModal, setShowMergeModal] = useState(false)
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false)
  const [bulkDeleteWithFiles, setBulkDeleteWithFiles] = useState(false)

  // Saved filters management
  const { savedFilters, saveFilter, deleteFilter } = useSavedFilters()

  // Get filters from URL params
  const { filters, setFilters, clearFilters } = useDesignFilters()

  // Build query params without pagination (infinite scroll handles that)
  const queryParams: Omit<DesignListParams, 'page'> = {
    page_size: 48, // Load more items per page for infinite scroll
    status: filters.status,
    channel_id: filters.channel_id,
    file_type: filters.file_type,
    multicolor: filters.multicolor,
    has_thangs_link: filters.has_thangs_link,
    designer: filters.designer,
    q: filters.q,
    sort_by: filters.sort_by || 'created_at',
    sort_order: filters.sort_order || 'DESC',
    tags: filters.tags,
    import_source_id: filters.import_source_id,
    import_source_folder_id: filters.import_source_folder_id,
  }

  // Infinite query for designs
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteDesigns(queryParams)

  // Mutations
  const mergeMutation = useMergeDesigns()
  const bulkDeleteMutation = useBulkDeleteDesigns()

  // Flatten infinite query pages into single array
  const designs = flattenInfiniteDesigns(data)
  const totalCount = getInfiniteDesignsTotal(data)

  // Event handlers
  const handleViewChange = useCallback((newView: ViewMode) => {
    setView(newView)
    setStoredView(newView)
  }, [])

  const handleSearchChange = useCallback((q: string) => {
    setFilters({ q: q || undefined })
    // Reset to custom filter when searching
    setActiveFilterId(q ? null : activeFilterId)
  }, [setFilters, activeFilterId])

  const handleSortChange = useCallback((sortBy: SortField, sortOrder: SortOrder) => {
    setFilters({ sort_by: sortBy, sort_order: sortOrder })
  }, [setFilters])

  const handleSelectFilter = useCallback((filterId: string, filterParams: Partial<DesignListParams>) => {
    setActiveFilterId(filterId)
    setStoredActiveFilter(filterId)
    // Clear existing filters and apply new ones
    clearFilters()
    if (Object.keys(filterParams).length > 0) {
      setFilters(filterParams)
    }
  }, [clearFilters, setFilters])

  const handleApplyCustomFilter = useCallback((filterParams: Partial<DesignListParams>) => {
    setActiveFilterId(null)
    clearFilters()
    setFilters(filterParams)
  }, [clearFilters, setFilters])

  const handleSaveCustomFilter = useCallback((label: string, filterParams: Partial<DesignListParams>) => {
    const saved = saveFilter(label, filterParams)
    setActiveFilterId(saved.id)
    setStoredActiveFilter(saved.id)
    clearFilters()
    setFilters(filterParams)
  }, [saveFilter, clearFilters, setFilters])

  const handleDeleteSavedFilter = useCallback((id: string) => {
    deleteFilter(id)
    if (activeFilterId === id) {
      setActiveFilterId('all')
      setStoredActiveFilter('all')
      clearFilters()
    }
  }, [deleteFilter, activeFilterId, clearFilters])

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

  // Get selected designs from loaded data
  const selectedDesigns = designs.filter((d) => selectedIds.has(d.id))

  return (
    <div className="h-full flex flex-col -m-6">
      {/* Main scrollable container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto"
      >
        {/* Sticky Toolbar */}
        <div className="sticky top-0 z-20 bg-bg-primary px-4 pt-4 pb-2">
          <DesignToolbar
            searchQuery={filters.q || ''}
            onSearchChange={handleSearchChange}
            sortBy={filters.sort_by || 'created_at'}
            sortOrder={filters.sort_order || 'DESC'}
            onSortChange={handleSortChange}
            view={view}
            onViewChange={handleViewChange}
            activeFilterId={activeFilterId}
            savedFilters={savedFilters}
            onSelectFilter={handleSelectFilter}
            onOpenCustomFilter={() => setShowCustomFilterModal(true)}
            onDeleteSavedFilter={handleDeleteSavedFilter}
            totalCount={totalCount}
          />
        </div>

        {/* Error state */}
        {error && (
          <div className="mx-4 mb-4 bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
            <p className="text-accent-danger">
              Failed to load designs: {(error as Error).message}
            </p>
          </div>
        )}

        {/* Design Grid with Infinite Scroll */}
        <InfiniteDesignGrid
          designs={designs}
          isLoading={isLoading}
          isFetchingNextPage={isFetchingNextPage}
          hasNextPage={hasNextPage ?? false}
          fetchNextPage={fetchNextPage}
          view={view}
          scrollRef={scrollRef}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelection}
        />
      </div>

      {/* Scroll to Top Button */}
      <ScrollToTopButton scrollRef={scrollRef} />

      {/* Selection Action Bar */}
      {selectedIds.size > 0 && (
        <div className="bg-bg-secondary border-t border-bg-tertiary p-4 flex items-center justify-between">
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

      {/* Custom Filter Modal */}
      <CustomFilterModal
        isOpen={showCustomFilterModal}
        onClose={() => setShowCustomFilterModal(false)}
        onApply={handleApplyCustomFilter}
        onSave={handleSaveCustomFilter}
      />

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
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-lg bg-bg-primary rounded-lg shadow-xl">
          <div className="flex items-center justify-between px-6 py-4 border-b border-bg-tertiary">
            <div>
              <h2 className="text-lg font-medium text-text-primary">Merge Designs</h2>
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
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={isPending ? undefined : onClose}
        aria-hidden="true"
      />
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md bg-bg-primary rounded-lg shadow-xl">
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

          <div className="p-6 space-y-4">
            <p className="text-text-secondary">
              Are you sure you want to delete {count} design{count !== 1 ? 's' : ''}?
              This action cannot be undone.
            </p>

            <div className="space-y-3 pt-2">
              <p className="text-sm text-text-muted">Choose what to delete:</p>
              <label className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary cursor-pointer hover:bg-bg-tertiary transition-colors">
                <input
                  type="radio"
                  name="bulkDeleteOption"
                  checked={!deleteFiles}
                  onChange={() => onDeleteFilesChange(false)}
                  className="mt-0.5 text-accent-primary focus:ring-accent-primary"
                />
                <div>
                  <p className="text-sm font-medium text-text-primary">Database only</p>
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
                  <p className="text-sm font-medium text-accent-danger">Database + Files</p>
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
