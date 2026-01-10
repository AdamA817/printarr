import { useState } from 'react'
import { Link } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { DesignCard } from './DesignCard'
import type { DesignListItem, PreviewSource } from '@/types/design'
import { getPreviewUrl } from '@/hooks/usePreviews'

interface FamilyCardProps {
  familyId: string
  designs: DesignListItem[]
  isExpanded?: boolean
  onToggleExpand?: () => void
  selectedIds?: Set<string>
  onToggleSelect?: (id: string, event?: React.MouseEvent) => void
  selectionMode?: boolean
}

// Preview source badge config
const previewSourceLabels: Record<PreviewSource, string> = {
  TELEGRAM: 'TG',
  ARCHIVE: 'AR',
  EMBEDDED_3MF: '3MF',
  THANGS: 'TH',
  RENDERED: 'RN',
}

// Extract base name from design title (remove variant suffix)
function extractBaseName(designs: DesignListItem[]): string {
  // Use the first design's title, try to extract base name
  if (designs.length === 0) return 'Unknown Family'

  const firstDesign = designs[0]
  const title = firstDesign.display_title

  // If there's a variant_name, try to strip it from the title
  if (firstDesign.variant_name) {
    // Common patterns: title_variant, title - variant, title (variant)
    const patterns = [
      new RegExp(`[_\\-\\s]+${escapeRegex(firstDesign.variant_name)}$`, 'i'),
      new RegExp(`\\s*\\(${escapeRegex(firstDesign.variant_name)}\\)$`, 'i'),
    ]
    for (const pattern of patterns) {
      const stripped = title.replace(pattern, '').trim()
      if (stripped && stripped !== title) {
        return stripped
      }
    }
  }

  // Fallback: use canonical title of first design
  return firstDesign.canonical_title || title
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Get the "best" status to show for a family (most progressed)
function getFamilyStatus(designs: DesignListItem[]): DesignListItem['status'] {
  const statusPriority: Record<DesignListItem['status'], number> = {
    ORGANIZED: 7,
    IMPORTING: 6,
    EXTRACTED: 5,
    EXTRACTING: 4,
    DOWNLOADED: 3,
    DOWNLOADING: 2,
    WANTED: 1,
    DISCOVERED: 0,
    FAILED: -1,
  }

  let bestStatus = designs[0]?.status || 'DISCOVERED'
  let bestPriority = statusPriority[bestStatus] ?? 0

  for (const design of designs) {
    const priority = statusPriority[design.status] ?? 0
    if (priority > bestPriority) {
      bestPriority = priority
      bestStatus = design.status
    }
  }

  return bestStatus
}

// Get the best preview from all variants
function getBestPreview(designs: DesignListItem[]) {
  // Prefer previews in order: THANGS, RENDERED, EMBEDDED_3MF, ARCHIVE, TELEGRAM
  const sourcePriority: Record<PreviewSource, number> = {
    THANGS: 4,
    RENDERED: 3,
    EMBEDDED_3MF: 2,
    ARCHIVE: 1,
    TELEGRAM: 0,
  }

  let bestPreview = designs[0]?.primary_preview
  let bestPriority = bestPreview ? (sourcePriority[bestPreview.source] ?? 0) : -1

  for (const design of designs) {
    if (design.primary_preview) {
      const priority = sourcePriority[design.primary_preview.source] ?? 0
      if (priority > bestPriority) {
        bestPriority = priority
        bestPreview = design.primary_preview
      }
    }
  }

  return bestPreview
}

export function FamilyCard({
  familyId,
  designs,
  isExpanded = false,
  onToggleExpand,
  selectedIds,
  onToggleSelect,
  selectionMode,
}: FamilyCardProps) {
  const [imageError, setImageError] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)

  const familyName = extractBaseName(designs)
  const designer = designs[0]?.display_designer || 'Unknown'
  const variantCount = designs.length
  const familyStatus = getFamilyStatus(designs)
  const preview = getBestPreview(designs)
  const hasPreview = preview && !imageError
  const previewUrl = preview ? getPreviewUrl(preview.file_path) : null

  // Check if any designs in family are selected
  const selectedInFamily = designs.filter(d => selectedIds?.has(d.id)).length
  const allInFamilySelected = selectedInFamily === designs.length

  const handleFamilySelect = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Toggle all designs in family
    for (const design of designs) {
      if (allInFamilySelected) {
        // Deselect all if all are selected
        if (selectedIds?.has(design.id)) {
          onToggleSelect?.(design.id, e)
        }
      } else {
        // Select all if not all selected
        if (!selectedIds?.has(design.id)) {
          onToggleSelect?.(design.id, e)
        }
      }
    }
  }

  const handleExpandClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onToggleExpand?.()
  }

  // Collapsed view
  if (!isExpanded) {
    return (
      <div className="block bg-bg-secondary rounded-lg overflow-hidden hover:ring-2 hover:ring-purple-500/50 transition-all group">
        {/* Thumbnail / Preview */}
        <div className="aspect-square bg-bg-tertiary flex items-center justify-center relative overflow-hidden">
          {/* Preview image or placeholder */}
          {hasPreview && previewUrl ? (
            <>
              {!imageLoaded && (
                <div className="absolute inset-0 bg-bg-tertiary animate-pulse" />
              )}
              <img
                src={previewUrl}
                alt={familyName}
                className={`w-full h-full object-cover transition-opacity ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
                loading="lazy"
                onLoad={() => setImageLoaded(true)}
                onError={() => setImageError(true)}
              />
            </>
          ) : (
            <span className="text-4xl opacity-50">
              <FamilyIcon className="w-12 h-12" />
            </span>
          )}

          {/* Selection checkbox */}
          {onToggleSelect && (
            <div
              onClick={handleFamilySelect}
              className={`absolute top-2 left-2 z-10 transition-opacity ${
                selectionMode || selectedInFamily > 0 ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
              }`}
            >
              <input
                type="checkbox"
                checked={allInFamilySelected}
                ref={(el) => {
                  if (el) el.indeterminate = selectedInFamily > 0 && !allInFamilySelected
                }}
                onChange={() => {}}
                className="w-5 h-5 rounded border-2 border-white bg-black/30 text-accent-primary focus:ring-accent-primary cursor-pointer"
              />
            </div>
          )}

          {/* Family overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

          {/* Variant count badge */}
          <div className="absolute top-2 right-2 flex flex-col gap-1 items-end">
            <span className="bg-purple-600/90 text-white text-xs px-2 py-1 rounded font-medium flex items-center gap-1.5">
              <FamilyIcon className="w-3.5 h-3.5" />
              {variantCount} variant{variantCount !== 1 ? 's' : ''}
            </span>

            {/* Preview source badge */}
            {preview && (
              <span
                className="bg-black/50 text-white/80 text-[8px] px-1 py-0.5 rounded"
                title={`Source: ${preview.source}`}
              >
                {previewSourceLabels[preview.source]}
              </span>
            )}
          </div>

          {/* Expand button */}
          <button
            onClick={handleExpandClick}
            className="absolute bottom-2 right-2 bg-purple-600/80 hover:bg-purple-600 text-white text-xs px-2 py-1 rounded transition-colors flex items-center gap-1"
          >
            <ChevronDownIcon className="w-3 h-3" />
            Expand
          </button>

          {/* Hover overlay */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
            <span className="text-white text-sm font-medium">Click to expand</span>
          </div>
        </div>

        {/* Card content */}
        <Link to={`/families/${familyId}`} className="block p-3">
          {/* Title */}
          <h3 className="text-text-primary font-medium truncate text-sm flex items-center gap-1.5" title={familyName}>
            <FamilyIcon className="w-4 h-4 text-purple-400 flex-shrink-0" />
            {familyName}
          </h3>

          {/* Designer */}
          <p className="text-text-secondary text-xs truncate mt-0.5" title={designer}>
            {designer}
          </p>

          {/* Footer: Status + Variant list */}
          <div className="mt-2 flex items-center justify-between gap-2">
            <StatusBadge status={familyStatus} size="sm" />
            <span className="text-text-muted text-[10px] truncate">
              {designs.slice(0, 2).map(d => d.variant_name || 'Base').join(', ')}
              {designs.length > 2 && '...'}
            </span>
          </div>
        </Link>
      </div>
    )
  }

  // Expanded view - show family header + all variant cards
  return (
    <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
      {/* Family header */}
      <div className="flex items-center justify-between mb-3">
        <Link to={`/families/${familyId}`} className="flex items-center gap-2 hover:text-purple-400 transition-colors">
          <FamilyIcon className="w-5 h-5 text-purple-400" />
          <div>
            <h3 className="text-text-primary font-medium text-sm">{familyName}</h3>
            <p className="text-text-secondary text-xs">{designer}</p>
          </div>
          <span className="bg-purple-600/80 text-white text-xs px-2 py-0.5 rounded ml-2">
            {variantCount} variant{variantCount !== 1 ? 's' : ''}
          </span>
        </Link>
        <button
          onClick={handleExpandClick}
          className="text-text-muted hover:text-text-primary transition-colors p-1"
          title="Collapse family"
        >
          <ChevronUpIcon className="w-5 h-5" />
        </button>
      </div>

      {/* Variant cards in a sub-grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {designs.map((design) => (
          <DesignCard
            key={design.id}
            design={design}
            isSelected={selectedIds?.has(design.id)}
            onToggleSelect={onToggleSelect}
            selectionMode={selectionMode}
            showActions={true}
          />
        ))}
      </div>
    </div>
  )
}

// Skeleton loader for family cards
export function FamilyCardSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden animate-pulse">
      <div className="aspect-square bg-bg-tertiary" />
      <div className="p-3 space-y-2">
        <div className="h-4 bg-bg-tertiary rounded w-3/4" />
        <div className="h-3 bg-bg-tertiary rounded w-1/2" />
        <div className="flex items-center justify-between mt-2">
          <div className="h-5 bg-bg-tertiary rounded w-16" />
          <div className="h-3 bg-bg-tertiary rounded w-20" />
        </div>
      </div>
    </div>
  )
}

// Icons
function FamilyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  )
}

function ChevronUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
    </svg>
  )
}
