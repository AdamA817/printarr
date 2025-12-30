import { useParams, Link } from 'react-router-dom'
import { useDesign } from '@/hooks/useDesigns'
import type { DesignStatus, ExternalMetadata } from '@/types/design'

// Status badge colors matching Radarr style
const statusColors: Record<DesignStatus, string> = {
  DISCOVERED: 'bg-text-muted text-text-primary',
  WANTED: 'bg-accent-primary text-white',
  DOWNLOADING: 'bg-accent-warning text-white',
  DOWNLOADED: 'bg-accent-success text-white',
  ORGANIZED: 'bg-accent-success text-white',
}

const statusLabels: Record<DesignStatus, string> = {
  DISCOVERED: 'Discovered',
  WANTED: 'Wanted',
  DOWNLOADING: 'Downloading',
  DOWNLOADED: 'Downloaded',
  ORGANIZED: 'Organized',
}

function StatusBadge({ status }: { status: DesignStatus }) {
  return (
    <span
      className={`px-3 py-1 rounded text-sm font-medium ${statusColors[status]}`}
    >
      {statusLabels[status]}
    </span>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return 'Unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function ThangsSection({ thangs }: { thangs: ExternalMetadata }) {
  return (
    <div className="bg-bg-tertiary rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-accent-primary font-medium">Thangs</span>
        <span className="text-xs px-2 py-0.5 rounded bg-accent-success/20 text-accent-success">
          Linked
        </span>
      </div>
      <div className="space-y-2 text-sm">
        {thangs.fetched_title && (
          <div>
            <span className="text-text-muted">Title: </span>
            <span className="text-text-primary">{thangs.fetched_title}</span>
          </div>
        )}
        {thangs.fetched_designer && (
          <div>
            <span className="text-text-muted">Designer: </span>
            <span className="text-text-primary">{thangs.fetched_designer}</span>
          </div>
        )}
        <a
          href={thangs.external_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-accent-primary hover:underline"
        >
          View on Thangs
          <ExternalLinkIcon className="w-4 h-4" />
        </a>
      </div>
    </div>
  )
}

function DesignDetailSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-8 bg-bg-tertiary rounded w-1/3" />
      <div className="h-6 bg-bg-tertiary rounded w-1/4" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-bg-secondary rounded-lg p-6 space-y-4">
          <div className="h-4 bg-bg-tertiary rounded w-1/2" />
          <div className="h-4 bg-bg-tertiary rounded w-3/4" />
          <div className="h-4 bg-bg-tertiary rounded w-2/3" />
        </div>
        <div className="bg-bg-secondary rounded-lg p-6 space-y-4">
          <div className="h-4 bg-bg-tertiary rounded w-1/2" />
          <div className="h-4 bg-bg-tertiary rounded w-3/4" />
        </div>
      </div>
    </div>
  )
}

export function DesignDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: design, isLoading, error } = useDesign(id || '')

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Link
          to="/designs"
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </Link>
        <DesignDetailSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Link
          to="/designs"
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </Link>
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load design: {(error as Error).message}
          </p>
        </div>
      </div>
    )
  }

  if (!design) {
    return (
      <div className="space-y-6">
        <Link
          to="/designs"
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </Link>
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <p className="text-text-secondary">Design not found</p>
        </div>
      </div>
    )
  }

  const thangsLink = design.external_metadata.find(
    (em) => em.source_type === 'THANGS'
  )
  const preferredSource = design.sources.find((s) => s.is_preferred) || design.sources[0]

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <Link
        to="/designs"
        className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
      >
        <BackIcon className="w-4 h-4" />
        Back to Designs
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {design.display_title}
          </h1>
          <p className="text-text-secondary mt-1">
            by {design.display_designer}
          </p>
        </div>
        <StatusBadge status={design.status} />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Details
            </h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-text-muted">File Types</dt>
                <dd className="text-text-primary mt-1">
                  {design.primary_file_types || 'Unknown'}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Total Size</dt>
                <dd className="text-text-primary mt-1">
                  {formatFileSize(design.total_size_bytes)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Multicolor</dt>
                <dd className="text-text-primary mt-1 capitalize">
                  {design.display_multicolor.toLowerCase()}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Added</dt>
                <dd className="text-text-primary mt-1">
                  {formatDate(design.created_at)}
                </dd>
              </div>
            </dl>
          </section>

          {/* Source Info */}
          {preferredSource && (
            <section className="bg-bg-secondary rounded-lg p-6">
              <h2 className="text-lg font-medium text-text-primary mb-4">
                Source
              </h2>
              <div className="space-y-4">
                <div>
                  <dt className="text-sm text-text-muted">Channel</dt>
                  <dd className="text-text-primary mt-1">
                    {preferredSource.channel.title}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-text-muted">Posted</dt>
                  <dd className="text-text-primary mt-1">
                    {formatDate(preferredSource.created_at)}
                  </dd>
                </div>
                {preferredSource.caption_snapshot && (
                  <div>
                    <dt className="text-sm text-text-muted mb-2">Caption</dt>
                    <dd className="text-text-secondary text-sm bg-bg-tertiary rounded-lg p-4 whitespace-pre-wrap">
                      {preferredSource.caption_snapshot}
                    </dd>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Additional Sources */}
          {design.sources.length > 1 && (
            <section className="bg-bg-secondary rounded-lg p-6">
              <h2 className="text-lg font-medium text-text-primary mb-4">
                Other Sources ({design.sources.length - 1})
              </h2>
              <div className="space-y-3">
                {design.sources
                  .filter((s) => s.id !== preferredSource?.id)
                  .map((source) => (
                    <div
                      key={source.id}
                      className="flex items-center justify-between py-2 border-b border-bg-tertiary last:border-0"
                    >
                      <span className="text-text-secondary">
                        {source.channel.title}
                      </span>
                      <span className="text-sm text-text-muted">
                        {formatDate(source.created_at)}
                      </span>
                    </div>
                  ))}
              </div>
            </section>
          )}
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Thangs Link */}
          {thangsLink ? (
            <ThangsSection thangs={thangsLink} />
          ) : (
            <div className="bg-bg-secondary rounded-lg p-4">
              <div className="flex items-center gap-2 text-text-muted">
                <span>Thangs</span>
                <span className="text-xs px-2 py-0.5 rounded bg-bg-tertiary">
                  Not linked
                </span>
              </div>
            </div>
          )}

          {/* Notes */}
          {design.notes && (
            <section className="bg-bg-secondary rounded-lg p-4">
              <h3 className="text-sm font-medium text-text-muted mb-2">Notes</h3>
              <p className="text-text-secondary text-sm whitespace-pre-wrap">
                {design.notes}
              </p>
            </section>
          )}

          {/* Metadata */}
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-muted mb-3">
              Metadata
            </h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-text-muted">Authority</dt>
                <dd className="text-text-primary capitalize">
                  {design.metadata_authority.toLowerCase()}
                </dd>
              </div>
              {design.metadata_confidence !== null && (
                <div className="flex justify-between">
                  <dt className="text-text-muted">Confidence</dt>
                  <dd className="text-text-primary">
                    {(design.metadata_confidence * 100).toFixed(0)}%
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-text-muted">Updated</dt>
                <dd className="text-text-primary">
                  {formatDate(design.updated_at)}
                </dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </div>
  )
}

// Icon Components

function BackIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 19l-7-7m0 0l7-7m-7 7h18"
      />
    </svg>
  )
}

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  )
}
