import { useState } from 'react'
import { Link } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import { DesignActions } from './DesignActions'
import { TagList } from './TagManager'
import type { DesignListItem, PreviewSource } from '@/types/design'
import { getPreviewUrl } from '@/hooks/usePreviews'

interface DesignCardProps {
  design: DesignListItem
  isSelected?: boolean
  onToggleSelect?: (id: string, event?: React.MouseEvent) => void
  selectionMode?: boolean
  showActions?: boolean
}

// File type icons (simple text representations)
const fileTypeIcons: Record<string, string> = {
  STL: '📐',
  '3MF': '📦',
  OBJ: '🔷',
  STEP: '⚙️',
  ZIP: '📁',
  RAR: '📁',
  '7Z': '📁',
}

function getFileTypeIcon(fileTypes: string[]): string {
  if (fileTypes.length === 0) return '📄'
  // Return icon for first recognized type
  for (const ft of fileTypes) {
    const upper = ft.toUpperCase()
    if (upper in fileTypeIcons) return fileTypeIcons[upper]
  }
  return '📄'
}

// Preview source badge config
const previewSourceLabels: Record<PreviewSource, string> = {
  TELEGRAM: 'TG',
  ARCHIVE: 'AR',
  EMBEDDED_3MF: '3MF',
  THANGS: 'TH',
  RENDERED: 'RN',
}

export function DesignCard({ design, isSelected, onToggleSelect, selectionMode, showActions = true }: DesignCardProps) {
  const [imageError, setImageError] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onToggleSelect?.(design.id, e)
  }

  const hasPreview = design.primary_preview && !imageError
  const previewUrl = design.primary_preview ? getPreviewUrl(design.primary_preview.file_path) : null

  return (
    <Link
      to={`/designs/${design.id}`}
      className={`block bg-bg-secondary rounded-lg overflow-hidden hover:ring-2 hover:ring-accent-primary/50 transition-all group ${
        isSelected ? 'ring-2 ring-accent-primary' : ''
      }`}
    >
      {/* Thumbnail / Preview */}
      <div className="aspect-square bg-bg-tertiary flex items-center justify-center relative overflow-hidden">
        {/* Preview image or placeholder */}
        {hasPreview && previewUrl ? (
          <>
            {/* Loading skeleton */}
            {!imageLoaded && (
              <div className="absolute inset-0 bg-bg-tertiary animate-pulse" />
            )}
            <img
              src={previewUrl}
              alt={design.display_title}
              className={`w-full h-full object-cover transition-opacity ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
              loading="lazy"
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageError(true)}
            />
          </>
        ) : (
          <span className="text-4xl opacity-50">
            {getFileTypeIcon(design.file_types)}
          </span>
        )}

        {/* Selection checkbox */}
        {onToggleSelect && (
          <div
            onClick={handleCheckboxClick}
            className={`absolute top-2 left-2 z-10 transition-opacity ${
              selectionMode || isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            }`}
          >
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => {}}
              className="w-5 h-5 rounded border-2 border-white bg-black/30 text-accent-primary focus:ring-accent-primary cursor-pointer"
            />
          </div>
        )}

        {/* Hover overlay with action button */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2 pointer-events-none">
          <span className="text-white text-sm font-medium">View Details</span>
          {showActions && (
            <div className="pointer-events-auto">
              <DesignActions
                designId={design.id}
                status={design.status}
                size="sm"
                variant="button"
              />
            </div>
          )}
        </div>

        {/* Top-right badges container */}
        <div className="absolute top-2 right-2 flex flex-col gap-1 items-end">
          {/* Family badge (DEC-044) */}
          {design.family_id && (
            <span
              className="bg-purple-600/80 text-white text-[9px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1"
              title={design.variant_name ? `Variant: ${design.variant_name}` : 'Part of a family'}
            >
              <FamilyIcon className="w-2.5 h-2.5" />
              {design.variant_name || 'Family'}
            </span>
          )}

          {/* Multicolor badge */}
          {design.multicolor === 'MULTI' && (
            <span
              className="bg-purple-500/80 text-white text-[9px] px-1.5 py-0.5 rounded font-medium"
              title="Multicolor / MMU compatible"
            >
              MMU
            </span>
          )}

          {/* Thangs indicator */}
          {design.has_thangs_link && (
            <span
              className="text-accent-primary bg-bg-primary/80 rounded px-1.5 py-0.5 text-xs"
              title="Linked to Thangs"
            >
              🔗
            </span>
          )}

          {/* Preview source badge */}
          {design.primary_preview && (
            <span
              className="bg-black/50 text-white/80 text-[8px] px-1 py-0.5 rounded"
              title={`Source: ${design.primary_preview.source}`}
            >
              {previewSourceLabels[design.primary_preview.source]}
            </span>
          )}
        </div>

        {/* Action button in corner (visible on hover, except for completed states) */}
        {showActions && (design.status === 'DISCOVERED' || design.status === 'WANTED' || design.status === 'DOWNLOADING' || design.status === 'FAILED') && (
          <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-auto">
            <DesignActions
              designId={design.id}
              status={design.status}
              size="sm"
              variant="icon"
            />
          </div>
        )}
      </div>

      {/* Card content */}
      <div className="p-3">
        {/* Title */}
        <h3 className="text-text-primary font-medium truncate text-sm" title={design.display_title}>
          {design.display_title}
        </h3>

        {/* Designer */}
        <p className="text-text-secondary text-xs truncate mt-0.5" title={design.display_designer}>
          {design.display_designer}
        </p>

        {/* Tags */}
        {design.tags && design.tags.length > 0 && (
          <div className="mt-1.5">
            <TagList tags={design.tags} maxVisible={2} />
          </div>
        )}

        {/* Footer: Status + File Types */}
        <div className="mt-2 flex items-center justify-between gap-2">
          <StatusBadge status={design.status} size="sm" />
          {design.file_types.length > 0 && (
            <span className="text-text-muted text-[10px] truncate">
              {design.file_types.slice(0, 2).join(', ')}
              {design.file_types.length > 2 && '...'}
            </span>
          )}
        </div>
      </div>
    </Link>
  )
}

// Skeleton loader for cards
export function DesignCardSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden animate-pulse">
      <div className="aspect-square bg-bg-tertiary" />
      <div className="p-3 space-y-2">
        <div className="h-4 bg-bg-tertiary rounded w-3/4" />
        <div className="h-3 bg-bg-tertiary rounded w-1/2" />
        <div className="flex items-center justify-between mt-2">
          <div className="h-5 bg-bg-tertiary rounded w-16" />
          <div className="h-3 bg-bg-tertiary rounded w-12" />
        </div>
      </div>
    </div>
  )
}

// Family icon (DEC-044)
function FamilyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}
