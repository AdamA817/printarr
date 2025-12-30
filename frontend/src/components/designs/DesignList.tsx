import { useNavigate } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import type { DesignListItem, SortField, SortOrder } from '@/types/design'

interface DesignListProps {
  designs: DesignListItem[]
  sortBy?: SortField
  sortOrder?: SortOrder
  onSort?: (field: SortField) => void
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Columns that can be sorted
type SortableColumn = {
  field: SortField
  label: string
}

const SORTABLE_COLUMNS: Record<string, SortableColumn | null> = {
  title: { field: 'canonical_title', label: 'Title' },
  designer: { field: 'canonical_designer', label: 'Designer' },
  channel: null, // Not sortable
  status: null, // Not sortable
  fileTypes: null, // Not sortable
  thangs: null, // Not sortable
  added: { field: 'created_at', label: 'Added' },
}

export function DesignList({ designs, sortBy, sortOrder, onSort }: DesignListProps) {
  const navigate = useNavigate()

  const handleRowClick = (id: string) => {
    navigate(`/designs/${id}`)
  }

  const renderColumnHeader = (
    column: string,
    label: string,
    className?: string
  ) => {
    const sortable = SORTABLE_COLUMNS[column]
    const isActive = sortable && sortBy === sortable.field
    const canSort = sortable && onSort

    if (!canSort) {
      return (
        <th className={`px-4 py-3 font-medium ${className || ''}`}>
          {label}
        </th>
      )
    }

    return (
      <th className={`px-4 py-3 font-medium ${className || ''}`}>
        <button
          onClick={() => onSort(sortable.field)}
          className="flex items-center gap-1 hover:text-text-primary transition-colors group"
        >
          {label}
          <SortIndicator active={isActive ?? false} direction={isActive ? sortOrder : undefined} />
        </button>
      </th>
    )
  }

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-bg-tertiary text-left text-sm text-text-secondary">
              {renderColumnHeader('title', 'Title')}
              {renderColumnHeader('designer', 'Designer')}
              {renderColumnHeader('channel', 'Channel')}
              {renderColumnHeader('status', 'Status')}
              {renderColumnHeader('fileTypes', 'File Types')}
              {renderColumnHeader('thangs', 'Thangs')}
              {renderColumnHeader('added', 'Added')}
            </tr>
          </thead>
          <tbody className="divide-y divide-bg-tertiary">
            {designs.map((design) => (
              <tr
                key={design.id}
                onClick={() => handleRowClick(design.id)}
                className="hover:bg-bg-tertiary/50 transition-colors cursor-pointer"
              >
                <td className="px-4 py-3">
                  <span className="text-text-primary font-medium truncate block max-w-xs">
                    {design.canonical_title}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-secondary">
                  {design.canonical_designer}
                </td>
                <td className="px-4 py-3 text-text-secondary">
                  {design.channel?.title || '—'}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={design.status} />
                </td>
                <td className="px-4 py-3 text-text-secondary text-sm">
                  {design.file_types.length > 0
                    ? design.file_types.join(', ')
                    : '—'}
                </td>
                <td className="px-4 py-3">
                  {design.has_thangs_link ? (
                    <span
                      className="text-accent-primary"
                      title="Linked to Thangs"
                    >
                      🔗
                    </span>
                  ) : (
                    <span className="text-text-muted">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-text-secondary text-sm">
                  {formatDate(design.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SortIndicator({ active, direction }: { active?: boolean; direction?: SortOrder }) {
  if (!active) {
    return (
      <span className="opacity-0 group-hover:opacity-50 transition-opacity">
        <ChevronUpDownIcon />
      </span>
    )
  }

  return direction === 'ASC' ? <ChevronUpIcon /> : <ChevronDownIcon />
}

function ChevronUpIcon() {
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
      <path d="M18 15l-6-6-6 6" />
    </svg>
  )
}

function ChevronDownIcon() {
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
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

function ChevronUpDownIcon() {
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
      <path d="M7 15l5 5 5-5" />
      <path d="M7 9l5-5 5 5" />
    </svg>
  )
}

// Skeleton loader for list
export function DesignListSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="bg-bg-secondary rounded-lg overflow-hidden">
        <div className="h-12 bg-bg-tertiary" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 border-t border-bg-tertiary">
            <div className="flex items-center h-full px-4 gap-4">
              <div className="h-4 bg-bg-tertiary rounded w-1/4" />
              <div className="h-4 bg-bg-tertiary rounded w-1/6" />
              <div className="h-4 bg-bg-tertiary rounded w-1/6" />
              <div className="h-6 bg-bg-tertiary rounded w-20" />
              <div className="h-4 bg-bg-tertiary rounded w-16" />
              <div className="h-4 bg-bg-tertiary rounded w-8" />
              <div className="h-4 bg-bg-tertiary rounded w-24" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
