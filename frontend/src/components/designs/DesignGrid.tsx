import { useRef, useCallback, useState, useEffect } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { DesignCard, DesignCardSkeleton } from './DesignCard'
import type { DesignListItem } from '@/types/design'

interface DesignGridProps {
  designs: DesignListItem[]
  selectedIds?: Set<string>
  onToggleSelect?: (id: string) => void
}

// Constants for grid layout
const GAP = 16 // gap-4 = 16px
const CARD_MIN_WIDTH = 180 // Minimum card width for responsive calculation
const CARD_CONTENT_HEIGHT = 100 // Fixed height for card info area (title, designer, tags, status)

// Breakpoint column counts matching Tailwind's grid-cols-* classes
function getColumnCount(containerWidth: number): number {
  // These match: grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6
  if (containerWidth >= 1280) return 6 // xl
  if (containerWidth >= 1024) return 5 // lg
  if (containerWidth >= 768) return 4 // md
  if (containerWidth >= 640) return 3 // sm
  return 2 // default
}

export function DesignGrid({ designs, selectedIds, onToggleSelect }: DesignGridProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const selectionMode = selectedIds && selectedIds.size > 0

  // Track container width for responsive columns
  useEffect(() => {
    const container = parentRef.current
    if (!container) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setContainerWidth(entry.contentRect.width)
      }
    })

    observer.observe(container)
    // Set initial width
    setContainerWidth(container.clientWidth)

    return () => observer.disconnect()
  }, [])

  // Calculate columns and row height based on container width
  const columns = getColumnCount(containerWidth)
  const cardWidth = containerWidth > 0 ? (containerWidth - GAP * (columns - 1)) / columns : CARD_MIN_WIDTH
  // Card height = square image (cardWidth) + fixed content area + gap
  const rowHeight = Math.round(cardWidth + CARD_CONTENT_HEIGHT) + GAP

  // Group designs into rows
  const rowCount = Math.ceil(designs.length / columns)

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => rowHeight, [rowHeight]),
    overscan: 3, // Render 3 extra rows above/below viewport
  })

  // If no width yet, render nothing to avoid layout thrashing
  if (containerWidth === 0) {
    return (
      <div ref={parentRef} className="w-full">
        <DesignGridSkeleton count={12} />
      </div>
    )
  }

  return (
    <div
      ref={parentRef}
      className="w-full h-[calc(100vh-200px)] min-h-[400px] overflow-auto"
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
          const rowStartIndex = virtualRow.index * columns
          const rowDesigns = designs.slice(rowStartIndex, rowStartIndex + columns)

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: virtualRow.size,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                }}
              >
                {rowDesigns.map((design) => (
                  <DesignCard
                    key={design.id}
                    design={design}
                    isSelected={selectedIds?.has(design.id)}
                    onToggleSelect={onToggleSelect}
                    selectionMode={selectionMode}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Skeleton loader for grid
export function DesignGridSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {[...Array(count)].map((_, i) => (
        <DesignCardSkeleton key={i} />
      ))}
    </div>
  )
}
