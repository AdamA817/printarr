import { useRef, useCallback, useState, useEffect, useMemo, type RefObject } from 'react'
import { DesignCard, DesignCardSkeleton } from './DesignCard'
import { FamilyCard } from './FamilyCard'
import { DesignList, DesignListSkeleton } from './DesignList'
import type { DesignListItem } from '@/types/design'
import type { ViewMode } from './ViewToggle'

interface InfiniteDesignGridProps {
  designs: DesignListItem[]
  isLoading: boolean
  isFetchingNextPage: boolean
  hasNextPage: boolean
  fetchNextPage: () => void
  view: ViewMode
  scrollRef: RefObject<HTMLDivElement | null>
  selectedIds?: Set<string>
  onToggleSelect?: (id: string, event?: React.MouseEvent) => void
}

// A single renderable card item - either a design or a collapsed family
type CardItem =
  | { type: 'design'; design: DesignListItem }
  | { type: 'family'; familyId: string; designs: DesignListItem[] }

// Group designs by family_id, returning a flat list of card items
// Families with only 1 member are treated as regular designs
function groupDesignsIntoCards(designs: DesignListItem[]): CardItem[] {
  // First pass: collect all designs by family_id
  const familyMap = new Map<string, DesignListItem[]>()
  const standaloneDesigns: DesignListItem[] = []

  for (const design of designs) {
    if (design.family_id) {
      if (!familyMap.has(design.family_id)) {
        familyMap.set(design.family_id, [])
      }
      familyMap.get(design.family_id)!.push(design)
    } else {
      standaloneDesigns.push(design)
    }
  }

  // Second pass: build flat list preserving rough order
  const items: CardItem[] = []
  const processedFamilies = new Set<string>()

  for (const design of designs) {
    if (design.family_id) {
      // Only add family once (when we first encounter it)
      if (!processedFamilies.has(design.family_id)) {
        processedFamilies.add(design.family_id)
        const familyDesigns = familyMap.get(design.family_id)!

        // Only treat as family if 2+ members, otherwise treat as standalone
        if (familyDesigns.length >= 2) {
          items.push({ type: 'family', familyId: design.family_id, designs: familyDesigns })
        } else {
          // Single-member "family" - just show as regular design
          items.push({ type: 'design', design: familyDesigns[0] })
        }
      }
    } else {
      items.push({ type: 'design', design })
    }
  }

  return items
}

function getColumnCount(containerWidth: number): number {
  if (containerWidth >= 1280) return 6
  if (containerWidth >= 1024) return 5
  if (containerWidth >= 768) return 4
  if (containerWidth >= 640) return 3
  return 2
}

export function InfiniteDesignGrid({
  designs,
  isLoading,
  isFetchingNextPage,
  hasNextPage,
  fetchNextPage,
  view,
  scrollRef,
  selectedIds,
  onToggleSelect,
}: InfiniteDesignGridProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const [expandedFamilies, setExpandedFamilies] = useState<Set<string>>(new Set())
  const selectionMode = selectedIds && selectedIds.size > 0

  // Group designs by family into flat card list
  const cardItems = useMemo(() => groupDesignsIntoCards(designs), [designs])

  const toggleFamilyExpanded = useCallback((familyId: string) => {
    setExpandedFamilies(prev => {
      const next = new Set(prev)
      if (next.has(familyId)) {
        next.delete(familyId)
      } else {
        next.add(familyId)
      }
      return next
    })
  }, [])

  // Track container width for responsive columns
  useEffect(() => {
    const container = contentRef.current
    if (!container) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setContainerWidth(entry.contentRect.width)
      }
    })

    observer.observe(container)
    setContainerWidth(container.clientWidth)

    return () => observer.disconnect()
  }, [])

  // Intersection observer for infinite scroll
  const loadMoreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const scrollElement = scrollRef.current
    if (!scrollElement) return

    // Don't set up observer while still loading initial data
    if (isLoading) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { root: scrollElement, threshold: 0.1, rootMargin: '100px' }
    )

    const el = loadMoreRef.current
    if (el) {
      observer.observe(el)
    }

    return () => {
      if (el) {
        observer.unobserve(el)
      }
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, scrollRef, isLoading])

  // Calculate columns
  const columns = view === 'grid' ? getColumnCount(containerWidth) : 1

  // Check if any families are expanded (need different rendering approach)
  const hasExpandedFamilies = cardItems.some(
    item => item.type === 'family' && expandedFamilies.has(item.familyId)
  )

  if (isLoading) {
    return (
      <div ref={contentRef} className="px-4">
        {view === 'grid' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {[...Array(12)].map((_, i) => (
              <DesignCardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <DesignListSkeleton />
        )}
      </div>
    )
  }

  if (designs.length === 0) {
    return (
      <div ref={contentRef} className="px-4 py-12 text-center">
        <div className="text-text-muted">
          <EmptyIcon className="w-16 h-16 mx-auto mb-4" />
          <p className="text-lg">No designs found</p>
          <p className="text-sm mt-2">Try adjusting your filters or search terms</p>
        </div>
      </div>
    )
  }

  // Show skeleton while getting initial width
  if (containerWidth === 0) {
    return (
      <div ref={contentRef} className="px-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {[...Array(12)].map((_, i) => (
            <DesignCardSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  // Helper to render a single card item (design or collapsed family)
  const renderCardItem = (item: CardItem) => {
    if (item.type === 'design') {
      return (
        <DesignCard
          key={item.design.id}
          design={item.design}
          isSelected={selectedIds?.has(item.design.id)}
          onToggleSelect={onToggleSelect}
          selectionMode={selectionMode}
        />
      )
    } else {
      return (
        <FamilyCard
          key={`family-${item.familyId}`}
          familyId={item.familyId}
          designs={item.designs}
          isExpanded={false}
          onToggleExpand={() => toggleFamilyExpanded(item.familyId)}
          selectedIds={selectedIds}
          onToggleSelect={onToggleSelect}
          selectionMode={selectionMode}
        />
      )
    }
  }

  return (
    <div ref={contentRef} className="px-4">
      {view === 'grid' ? (
        hasExpandedFamilies ? (
          // Has expanded families - need to break grid around them
          <div className="space-y-4">
            {(() => {
              const elements: React.ReactNode[] = []
              let currentBatch: CardItem[] = []

              const flushBatch = () => {
                if (currentBatch.length > 0) {
                  elements.push(
                    <div
                      key={`batch-${currentBatch[0].type === 'design' ? currentBatch[0].design.id : currentBatch[0].familyId}`}
                      className="grid gap-4"
                      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
                    >
                      {currentBatch.map(renderCardItem)}
                    </div>
                  )
                  currentBatch = []
                }
              }

              for (const item of cardItems) {
                if (item.type === 'family' && expandedFamilies.has(item.familyId)) {
                  // Expanded family - flush batch, render full-width
                  flushBatch()
                  elements.push(
                    <FamilyCard
                      key={`family-expanded-${item.familyId}`}
                      familyId={item.familyId}
                      designs={item.designs}
                      isExpanded={true}
                      onToggleExpand={() => toggleFamilyExpanded(item.familyId)}
                      selectedIds={selectedIds}
                      onToggleSelect={onToggleSelect}
                      selectionMode={selectionMode}
                    />
                  )
                } else {
                  // Add to current batch
                  currentBatch.push(item)
                }
              }

              // Flush remaining batch
              flushBatch()

              return elements
            })()}
          </div>
        ) : (
          // No expanded families - render all cards inline in one grid
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
          >
            {cardItems.map(renderCardItem)}
          </div>
        )
      ) : (
        // List View (not virtualized for simplicity - could be added later)
        <DesignList
          designs={designs}
          selectedIds={selectedIds}
          onToggleSelect={onToggleSelect}
        />
      )}

      {/* Load more trigger */}
      <div ref={loadMoreRef}>
        {isFetchingNextPage && (
          <div className="py-6">
            {view === 'grid' ? (
              // Show skeleton cards while loading more
              <div
                className="grid gap-4 opacity-60"
                style={{
                  gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                }}
              >
                {[...Array(Math.min(columns, 6))].map((_, i) => (
                  <DesignCardSkeleton key={`loading-${i}`} />
                ))}
              </div>
            ) : (
              // Show skeleton rows for list view
              <div className="space-y-2 opacity-60">
                {[...Array(3)].map((_, i) => (
                  <div key={`loading-${i}`} className="h-14 bg-bg-secondary rounded animate-pulse" />
                ))}
              </div>
            )}
            <div className="flex items-center justify-center gap-2 text-text-muted mt-4">
              <LoadingSpinner />
              <span className="text-sm">Loading more designs...</span>
            </div>
          </div>
        )}
        {!isFetchingNextPage && hasNextPage && (
          // Invisible trigger area
          <div className="h-20" />
        )}
        {!hasNextPage && designs.length > 0 && (
          <div className="h-16 flex items-center justify-center">
            <span className="text-sm text-text-muted">
              All {designs.length.toLocaleString()} designs loaded
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" />
      <line x1="9" y1="13" x2="15" y2="13" />
    </svg>
  )
}

function LoadingSpinner() {
  return (
    <svg
      className="animate-spin h-5 w-5"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
