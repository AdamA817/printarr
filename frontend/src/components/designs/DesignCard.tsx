import { Link } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import type { DesignListItem } from '@/types/design'

interface DesignCardProps {
  design: DesignListItem
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

export function DesignCard({ design }: DesignCardProps) {
  return (
    <Link
      to={`/designs/${design.id}`}
      className="block bg-bg-secondary rounded-lg overflow-hidden hover:ring-2 hover:ring-accent-primary/50 transition-all group"
    >
      {/* Thumbnail placeholder */}
      <div className="aspect-square bg-bg-tertiary flex items-center justify-center relative">
        <span className="text-4xl opacity-50">
          {getFileTypeIcon(design.file_types)}
        </span>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white text-sm font-medium">View Details</span>
        </div>

        {/* Thangs indicator */}
        {design.has_thangs_link && (
          <span
            className="absolute top-2 right-2 text-accent-primary bg-bg-primary/80 rounded px-1.5 py-0.5 text-xs"
            title="Linked to Thangs"
          >
            🔗
          </span>
        )}
      </div>

      {/* Card content */}
      <div className="p-3">
        {/* Title */}
        <h3 className="text-text-primary font-medium truncate text-sm" title={design.canonical_title}>
          {design.canonical_title}
        </h3>

        {/* Designer */}
        <p className="text-text-secondary text-xs truncate mt-0.5" title={design.canonical_designer}>
          {design.canonical_designer}
        </p>

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
