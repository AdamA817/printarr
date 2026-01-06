import { useState, useRef, useEffect } from 'react'
import { PREDEFINED_FILTERS, type SavedFilter } from '@/hooks/useSavedFilters'
import type { DesignListParams } from '@/types/design'

interface FilterDropdownProps {
  activeFilterId: string | null
  savedFilters: SavedFilter[]
  onSelectFilter: (filterId: string, filters: Partial<DesignListParams>) => void
  onOpenCustomFilter: () => void
  onDeleteSavedFilter?: (id: string) => void
}

export function FilterDropdown({
  activeFilterId,
  savedFilters,
  onSelectFilter,
  onOpenCustomFilter,
  onDeleteSavedFilter,
}: FilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Close on escape
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
    }
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen])

  const activeLabel = getActiveFilterLabel(activeFilterId, savedFilters)
  const hasActiveFilter = activeFilterId && activeFilterId !== 'all'

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          hasActiveFilter
            ? 'bg-accent-primary text-white'
            : 'bg-bg-tertiary text-text-primary hover:bg-bg-secondary'
        }`}
      >
        <FilterIcon />
        <span>{activeLabel}</span>
        <ChevronDownIcon className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-bg-secondary border border-border-primary rounded-lg shadow-xl z-50 overflow-hidden">
          {/* Predefined Filters */}
          <div className="py-1">
            {PREDEFINED_FILTERS.map((filter) => (
              <button
                key={filter.id}
                onClick={() => {
                  onSelectFilter(filter.id, filter.filters)
                  setIsOpen(false)
                }}
                className={`w-full px-4 py-2 text-left text-sm transition-colors ${
                  activeFilterId === filter.id
                    ? 'bg-accent-primary/20 text-accent-primary'
                    : 'text-text-primary hover:bg-bg-tertiary'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          {/* Saved Custom Filters */}
          {savedFilters.length > 0 && (
            <>
              <div className="border-t border-border-primary" />
              <div className="py-1">
                <div className="px-4 py-1 text-xs text-text-muted uppercase tracking-wider">
                  Saved Filters
                </div>
                {savedFilters.map((filter) => (
                  <div
                    key={filter.id}
                    className={`flex items-center justify-between px-4 py-2 transition-colors ${
                      activeFilterId === filter.id
                        ? 'bg-accent-primary/20'
                        : 'hover:bg-bg-tertiary'
                    }`}
                  >
                    <button
                      onClick={() => {
                        onSelectFilter(filter.id, filter.filters)
                        setIsOpen(false)
                      }}
                      className={`flex-1 text-left text-sm ${
                        activeFilterId === filter.id
                          ? 'text-accent-primary'
                          : 'text-text-primary'
                      }`}
                    >
                      {filter.label}
                    </button>
                    {onDeleteSavedFilter && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteSavedFilter(filter.id)
                        }}
                        className="p-1 text-text-muted hover:text-accent-danger transition-colors"
                        title="Delete filter"
                      >
                        <TrashIcon />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Custom Filter Option */}
          <div className="border-t border-border-primary" />
          <div className="py-1">
            <button
              onClick={() => {
                onOpenCustomFilter()
                setIsOpen(false)
              }}
              className="w-full px-4 py-2 text-left text-sm text-accent-primary hover:bg-bg-tertiary transition-colors flex items-center gap-2"
            >
              <PlusIcon />
              Custom Filter...
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function getActiveFilterLabel(
  activeFilterId: string | null,
  savedFilters: SavedFilter[]
): string {
  if (!activeFilterId) return 'All'

  const predefined = PREDEFINED_FILTERS.find((f) => f.id === activeFilterId)
  if (predefined) return predefined.label

  const saved = savedFilters.find((f) => f.id === activeFilterId)
  if (saved) return saved.label

  return 'Custom'
}

function FilterIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
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

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  )
}
