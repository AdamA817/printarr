import { SearchBox } from './SearchBox'
import { SortControls } from './SortControls'
import { ViewToggle, type ViewMode } from './ViewToggle'
import { FilterDropdown } from './FilterDropdown'
import type { SavedFilter } from '@/hooks/useSavedFilters'
import type { DesignListParams, SortField, SortOrder } from '@/types/design'

interface DesignToolbarProps {
  // Search
  searchQuery: string
  onSearchChange: (query: string) => void

  // Sort
  sortBy: SortField
  sortOrder: SortOrder
  onSortChange: (sortBy: SortField, sortOrder: SortOrder) => void

  // View
  view: ViewMode
  onViewChange: (view: ViewMode) => void

  // Filters
  activeFilterId: string | null
  savedFilters: SavedFilter[]
  onSelectFilter: (filterId: string, filters: Partial<DesignListParams>) => void
  onOpenCustomFilter: () => void
  onDeleteSavedFilter?: (id: string) => void

  // Stats
  totalCount?: number
}

export function DesignToolbar({
  searchQuery,
  onSearchChange,
  sortBy,
  sortOrder,
  onSortChange,
  view,
  onViewChange,
  activeFilterId,
  savedFilters,
  onSelectFilter,
  onOpenCustomFilter,
  onDeleteSavedFilter,
  totalCount,
}: DesignToolbarProps) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-4 bg-bg-secondary rounded-lg">
      {/* Left side: Filter + Search */}
      <div className="flex items-center gap-3 flex-1 w-full sm:w-auto">
        <FilterDropdown
          activeFilterId={activeFilterId}
          savedFilters={savedFilters}
          onSelectFilter={onSelectFilter}
          onOpenCustomFilter={onOpenCustomFilter}
          onDeleteSavedFilter={onDeleteSavedFilter}
        />

        <div className="flex-1 max-w-md">
          <SearchBox
            value={searchQuery}
            onChange={onSearchChange}
            placeholder="Search designs..."
          />
        </div>
      </div>

      {/* Right side: Count + Sort + View */}
      <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
        {totalCount !== undefined && (
          <span className="text-sm text-text-muted">
            {totalCount.toLocaleString()} design{totalCount !== 1 ? 's' : ''}
          </span>
        )}

        <SortControls
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSortChange={onSortChange}
        />

        <ViewToggle view={view} onChange={onViewChange} />
      </div>
    </div>
  )
}
