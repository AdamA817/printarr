/**
 * PreviewGallery - Image gallery with lightbox for design previews (v0.7)
 *
 * Features:
 * - Large primary preview at top
 * - Thumbnail strip below for other images
 * - Source badge on each image (TG, Archive, 3MF, Thangs, Rendered)
 * - Lightbox for full-size viewing with navigation
 * - Keyboard support (arrows, Escape)
 * - "Set as Primary" button on each thumbnail
 */
import { useState, useCallback } from 'react'
import Lightbox from 'yet-another-react-lightbox'
import 'yet-another-react-lightbox/styles.css'
import type { Preview, PreviewSource } from '@/types/design'
import { getPreviewUrl } from '@/hooks/usePreviews'

interface PreviewGalleryProps {
  previews: Preview[]
  primaryId?: string
  onSetPrimary?: (previewId: string) => void
  isSettingPrimary?: boolean
}

// Source badge labels and colors
const sourceBadgeConfig: Record<PreviewSource, { label: string; className: string }> = {
  TELEGRAM: { label: 'TG', className: 'bg-blue-500/80 text-white' },
  ARCHIVE: { label: 'AR', className: 'bg-orange-500/80 text-white' },
  EMBEDDED_3MF: { label: '3MF', className: 'bg-purple-500/80 text-white' },
  THANGS: { label: 'TH', className: 'bg-green-500/80 text-white' },
  RENDERED: { label: 'RN', className: 'bg-accent-primary/80 text-white' },
}

function SourceBadge({ source, size = 'md' }: { source: PreviewSource; size?: 'sm' | 'md' }) {
  const config = sourceBadgeConfig[source]
  const sizeClasses = size === 'sm' ? 'text-[9px] px-1 py-0.5' : 'text-[10px] px-1.5 py-0.5'

  return (
    <span className={`rounded font-medium ${sizeClasses} ${config.className}`}>
      {config.label}
    </span>
  )
}

function NoPreviewPlaceholder() {
  return (
    <div className="aspect-video bg-bg-tertiary rounded-lg flex flex-col items-center justify-center text-text-muted">
      <ImageIcon className="w-16 h-16 mb-2 opacity-50" />
      <span className="text-sm">No preview available</span>
    </div>
  )
}

export function PreviewGallery({
  previews,
  primaryId,
  onSetPrimary,
  isSettingPrimary = false,
}: PreviewGalleryProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [lightboxIndex, setLightboxIndex] = useState(0)
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set())

  // Sort previews: primary first, then by sort_order
  const sortedPreviews = [...previews].sort((a, b) => {
    if (a.id === primaryId) return -1
    if (b.id === primaryId) return 1
    if (a.is_primary && !b.is_primary) return -1
    if (!a.is_primary && b.is_primary) return 1
    return a.sort_order - b.sort_order
  })

  const primaryPreview = sortedPreviews.find((p) => p.id === primaryId || p.is_primary) || sortedPreviews[0]
  const otherPreviews = sortedPreviews.filter((p) => p !== primaryPreview)

  const handleImageError = useCallback((previewId: string) => {
    setImageErrors((prev) => new Set(prev).add(previewId))
  }, [])

  const openLightbox = useCallback((index: number) => {
    setLightboxIndex(index)
    setLightboxOpen(true)
  }, [])

  // Prepare slides for lightbox
  const slides = sortedPreviews
    .filter((p) => !imageErrors.has(p.id))
    .map((preview) => ({
      src: getPreviewUrl(preview.file_path),
      alt: preview.original_filename || 'Preview image',
      width: preview.width || undefined,
      height: preview.height || undefined,
    }))

  if (previews.length === 0) {
    return <NoPreviewPlaceholder />
  }

  return (
    <div className="space-y-3">
      {/* Primary Preview */}
      {primaryPreview && !imageErrors.has(primaryPreview.id) && (
        <div
          className="relative aspect-video bg-bg-tertiary rounded-lg overflow-hidden cursor-pointer group"
          onClick={() => openLightbox(0)}
        >
          <img
            src={getPreviewUrl(primaryPreview.file_path)}
            alt={primaryPreview.original_filename || 'Primary preview'}
            className="w-full h-full object-contain"
            onError={() => handleImageError(primaryPreview.id)}
            loading="lazy"
          />

          {/* Source badge */}
          <div className="absolute top-2 right-2">
            <SourceBadge source={primaryPreview.source} />
          </div>

          {/* Hover overlay */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <span className="text-white text-sm font-medium flex items-center gap-2">
              <ExpandIcon className="w-5 h-5" />
              View Full Size
            </span>
          </div>

          {/* Dimensions */}
          {primaryPreview.width && primaryPreview.height && (
            <div className="absolute bottom-2 left-2 text-[10px] text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
              {primaryPreview.width} × {primaryPreview.height}
            </div>
          )}
        </div>
      )}

      {/* Thumbnail Strip */}
      {otherPreviews.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {otherPreviews.map((preview, index) => {
            if (imageErrors.has(preview.id)) return null

            const lightboxIdx = sortedPreviews.indexOf(preview)

            return (
              <div
                key={preview.id}
                className="relative flex-shrink-0 group"
              >
                {/* Thumbnail */}
                <button
                  type="button"
                  onClick={() => openLightbox(lightboxIdx)}
                  className="w-20 h-20 rounded-lg overflow-hidden bg-bg-tertiary border-2 border-transparent hover:border-accent-primary transition-colors focus:outline-none focus:ring-2 focus:ring-accent-primary"
                >
                  <img
                    src={getPreviewUrl(preview.file_path)}
                    alt={preview.original_filename || `Preview ${index + 2}`}
                    className="w-full h-full object-cover"
                    onError={() => handleImageError(preview.id)}
                    loading="lazy"
                  />
                </button>

                {/* Source badge */}
                <div className="absolute top-1 right-1">
                  <SourceBadge source={preview.source} size="sm" />
                </div>

                {/* Set as Primary button */}
                {onSetPrimary && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onSetPrimary(preview.id)
                    }}
                    disabled={isSettingPrimary}
                    className="absolute bottom-1 left-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity text-[9px] px-1 py-0.5 rounded bg-black/70 text-white hover:bg-black/90 disabled:opacity-50"
                    title="Set as primary preview"
                  >
                    {isSettingPrimary ? '...' : 'Set Primary'}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Preview Count */}
      {previews.length > 1 && (
        <div className="text-xs text-text-muted flex items-center gap-1">
          <ImageIcon className="w-3.5 h-3.5" />
          {previews.length} preview{previews.length !== 1 ? 's' : ''}
        </div>
      )}

      {/* Lightbox */}
      <Lightbox
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        index={lightboxIndex}
        slides={slides}
        styles={{
          container: { backgroundColor: 'rgba(0, 0, 0, 0.9)' },
        }}
      />
    </div>
  )
}

// Skeleton loader for gallery
export function PreviewGallerySkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="aspect-video bg-bg-tertiary rounded-lg" />
      <div className="flex gap-2">
        <div className="w-20 h-20 bg-bg-tertiary rounded-lg" />
        <div className="w-20 h-20 bg-bg-tertiary rounded-lg" />
        <div className="w-20 h-20 bg-bg-tertiary rounded-lg" />
      </div>
    </div>
  )
}

// Icon Components

function ImageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  )
}

function ExpandIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
      />
    </svg>
  )
}
