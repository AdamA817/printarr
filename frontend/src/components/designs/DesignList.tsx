import { useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVirtualizer } from '@tanstack/react-virtual'
import { StatusBadge } from './StatusBadge'
import { DesignActions } from './DesignActions'
import type { DesignListItem, SortField, SortOrder } from '@/types/design'

interface DesignListProps {
  designs: DesignListItem[]
  sortBy?: SortField
  sortOrder?: SortOrder
  onSort?: (field: SortField) => void
  selectedIds?: Set<string>
  onToggleSelect?: (id: string, event?: React.MouseEvent) => void
  showActions?: boolean
}

// Row height for virtualization (matches py-3 padding + content)
const ROW_HEIGHT = 56

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

// Column widths for flex layout (matching header and rows)
const COLUMN_WIDTHS = {
  checkbox: 'w-10 flex-shrink-0',
  title: 'flex-1 min-w-[200px]',
  designer: 'w-32 flex-shrink-0',
  channel: 'w-32 flex-shrink-0',
  status: 'w-28 flex-shrink-0',
  fileTypes: 'w-24 flex-shrink-0',
  thangs: 'w-16 flex-shrink-0',
  added: 'w-28 flex-shrink-0',
  actions: 'w-24 flex-shrink-0',
}

export function DesignList({ designs, sortBy, sortOrder, onSort, selectedIds, onToggleSelect, showActions = true }: DesignListProps) {
  const navigate = useNavigate()
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: designs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => ROW_HEIGHT, []),
    overscan: 10, // Render extra rows for smooth scrolling
  })

  const handleRowClick = (id: string, e: React.MouseEvent) => {
    // Don't navigate if clicking on checkbox or action buttons
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || target.closest('button')) return
    navigate(`/designs/${id}`)
  }

  const handleCheckboxClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    onToggleSelect?.(id, e)
  }

  const renderColumnHeader = (
    column: string,
    label: string,
    widthClass: string
  ) => {
    const sortable = SORTABLE_COLUMNS[column]
    const isActive = sortable && sortBy === sortable.field
    const canSort = sortable && onSort

    if (!canSort) {
      return (
        <div className={`px-4 py-3 font-medium ${widthClass}`}>
          {label}
        </div>
      )
    }

    return (
      <div className={`px-4 py-3 font-medium ${widthClass}`}>
        <button
          onClick={() => onSort(sortable.field)}
          className="flex items-center gap-1 hover:text-text-primary transition-colors group"
        >
          {label}
          <SortIndicator active={isActive ?? false} direction={isActive ? sortOrder : undefined} />
        </button>
      </div>
    )
  }

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      {/* Fixed header using flex layout */}
      <div className="flex items-center bg-bg-tertiary text-left text-sm text-text-secondary">
        {onToggleSelect && (
          <div className={`px-4 py-3 ${COLUMN_WIDTHS.checkbox}`}></div>
        )}
        {renderColumnHeader('title', 'Title', COLUMN_WIDTHS.title)}
        {renderColumnHeader('designer', 'Designer', COLUMN_WIDTHS.designer)}
        {renderColumnHeader('channel', 'Channel', COLUMN_WIDTHS.channel)}
        {renderColumnHeader('status', 'Status', COLUMN_WIDTHS.status)}
        {renderColumnHeader('fileTypes', 'File Types', COLUMN_WIDTHS.fileTypes)}
        {renderColumnHeader('thangs', 'Thangs', COLUMN_WIDTHS.thangs)}
        {renderColumnHeader('added', 'Added', COLUMN_WIDTHS.added)}
        {showActions && <div className={`px-4 py-3 font-medium ${COLUMN_WIDTHS.actions}`}>Actions</div>}
      </div>

      {/* Virtualized body */}
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
            const design = designs[virtualRow.index]
            return (
              <div
                key={design.id}
                onClick={(e) => handleRowClick(design.id, e)}
                className={`flex items-center hover:bg-bg-tertiary/50 transition-colors cursor-pointer border-b border-bg-tertiary ${
                  selectedIds?.has(design.id) ? 'bg-accent-primary/10' : ''
                }`}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: virtualRow.size,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                {onToggleSelect && (
                  <div className={`px-4 py-3 ${COLUMN_WIDTHS.checkbox}`}>
                    <input
                      type="checkbox"
                      checked={selectedIds?.has(design.id) || false}
                      onChange={() => {}}
                      onClick={(e) => handleCheckboxClick(e, design.id)}
                      className="w-4 h-4 rounded border-bg-tertiary bg-bg-tertiary text-accent-primary focus:ring-accent-primary cursor-pointer"
                    />
                  </div>
                )}
                <div className={`px-4 py-3 ${COLUMN_WIDTHS.title}`}>
                  <span className="text-text-primary font-medium truncate block">
                    {design.canonical_title}
                  </span>
                </div>
                <div className={`px-4 py-3 text-text-secondary truncate ${COLUMN_WIDTHS.designer}`}>
                  {design.canonical_designer}
                </div>
                <div className={`px-4 py-3 text-text-secondary truncate ${COLUMN_WIDTHS.channel}`}>
                  {design.channel?.title || '—'}
                </div>
                <div className={`px-4 py-3 ${COLUMN_WIDTHS.status}`}>
                  <StatusBadge status={design.status} />
                </div>
                <div className={`px-4 py-3 text-text-secondary text-sm truncate ${COLUMN_WIDTHS.fileTypes}`}>
                  {design.file_types.length > 0
                    ? design.file_types.join(', ')
                    : '—'}
                </div>
                <div className={`px-4 py-3 ${COLUMN_WIDTHS.thangs}`}>
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
                </div>
                <div className={`px-4 py-3 text-text-secondary text-sm ${COLUMN_WIDTHS.added}`}>
                  {formatDate(design.created_at)}
                </div>
                {showActions && (
                  <div className={`px-4 py-3 ${COLUMN_WIDTHS.actions}`}>
                    <DesignActions
                      designId={design.id}
                      status={design.status}
                      size="sm"
                      variant="icon"
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
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
