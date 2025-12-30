import type { SortField, SortOrder } from '@/types/design'

interface SortControlsProps {
  sortBy: SortField
  sortOrder: SortOrder
  onSortChange: (sortBy: SortField, sortOrder: SortOrder) => void
}

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'created_at', label: 'Date Added' },
  { value: 'canonical_title', label: 'Title' },
  { value: 'canonical_designer', label: 'Designer' },
  { value: 'total_size_bytes', label: 'Size' },
]

export function SortControls({ sortBy, sortOrder, onSortChange }: SortControlsProps) {
  const handleFieldChange = (field: SortField) => {
    // If clicking same field, toggle direction
    if (field === sortBy) {
      onSortChange(field, sortOrder === 'ASC' ? 'DESC' : 'ASC')
    } else {
      // New field, default to DESC for date, ASC for text fields
      const defaultOrder = field === 'created_at' || field === 'total_size_bytes' ? 'DESC' : 'ASC'
      onSortChange(field, defaultOrder)
    }
  }

  const handleOrderToggle = () => {
    onSortChange(sortBy, sortOrder === 'ASC' ? 'DESC' : 'ASC')
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-text-muted text-sm hidden sm:inline">Sort by:</span>
      <select
        value={sortBy}
        onChange={(e) => handleFieldChange(e.target.value as SortField)}
        className="bg-bg-tertiary border-0 rounded px-3 py-1.5 text-sm text-text-primary focus:ring-accent-primary"
      >
        {SORT_OPTIONS.map(({ value, label }) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <button
        onClick={handleOrderToggle}
        className="p-1.5 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
        title={sortOrder === 'ASC' ? 'Ascending' : 'Descending'}
        aria-label={`Sort ${sortOrder === 'ASC' ? 'ascending' : 'descending'}`}
      >
        {sortOrder === 'ASC' ? <SortAscIcon /> : <SortDescIcon />}
      </button>
    </div>
  )
}

function SortAscIcon() {
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
      <path d="M12 5v14" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )
}

function SortDescIcon() {
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
      <path d="M12 5v14" />
      <path d="M19 12l-7 7-7-7" />
    </svg>
  )
}
