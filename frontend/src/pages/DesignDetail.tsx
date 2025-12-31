import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  useDesign,
  useUnlinkFromThangs,
  useRefreshMetadata,
  useLinkToThangsByUrl,
  useUpdateDesign,
  useUnmergeDesign,
} from '@/hooks/useDesigns'
import { ThangsSearchModal, DownloadSection } from '@/components/designs'
import type {
  DesignStatus,
  ExternalMetadata,
  MetadataAuthority,
} from '@/types/design'

// Status badge colors matching Radarr style
const statusColors: Record<DesignStatus, string> = {
  DISCOVERED: 'bg-text-muted text-text-primary',
  WANTED: 'bg-accent-primary text-white',
  DOWNLOADING: 'bg-accent-warning text-white',
  DOWNLOADED: 'bg-accent-success text-white',
  EXTRACTING: 'bg-accent-warning text-white',
  EXTRACTED: 'bg-accent-success text-white',
  IMPORTING: 'bg-accent-warning text-white',
  ORGANIZED: 'bg-accent-success text-white',
  FAILED: 'bg-accent-danger text-white',
}

const statusLabels: Record<DesignStatus, string> = {
  DISCOVERED: 'Discovered',
  WANTED: 'Wanted',
  DOWNLOADING: 'Downloading',
  DOWNLOADED: 'Downloaded',
  EXTRACTING: 'Extracting',
  EXTRACTED: 'Extracted',
  IMPORTING: 'Importing',
  ORGANIZED: 'Organized',
  FAILED: 'Failed',
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

function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateString)
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return 'Unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

// Metadata source indicator component
function MetadataSourceBadge({ authority }: { authority: MetadataAuthority }) {
  const badgeConfig: Record<MetadataAuthority, { label: string; className: string }> = {
    TELEGRAM: { label: 'Telegram', className: 'bg-blue-500/20 text-blue-400' },
    THANGS: { label: 'Thangs', className: 'bg-purple-500/20 text-purple-400' },
    PRINTABLES: { label: 'Printables', className: 'bg-orange-500/20 text-orange-400' },
    USER: { label: 'User', className: 'bg-green-500/20 text-green-400' },
  }

  const config = badgeConfig[authority]
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}

// Edited indicator for user overrides
function EditedBadge() {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-warning/20 text-accent-warning font-medium ml-1">
      edited
    </span>
  )
}

interface ThangsSectionProps {
  designId: string
  thangs: ExternalMetadata | null
  onSearchThangs: () => void
}

function ThangsSection({ designId, thangs, onSearchThangs }: ThangsSectionProps) {
  const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false)
  const [showLinkInput, setShowLinkInput] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [linkError, setLinkError] = useState<string | null>(null)

  const unlinkMutation = useUnlinkFromThangs()
  const refreshMutation = useRefreshMetadata()
  const linkByUrlMutation = useLinkToThangsByUrl()

  const handleUnlink = async () => {
    try {
      await unlinkMutation.mutateAsync(designId)
      setShowUnlinkConfirm(false)
    } catch (err) {
      console.error('Failed to unlink:', err)
    }
  }

  const handleRefresh = async () => {
    try {
      await refreshMutation.mutateAsync(designId)
    } catch (err) {
      console.error('Failed to refresh metadata:', err)
    }
  }

  const handleLinkByUrl = async () => {
    if (!linkUrl.trim()) return
    setLinkError(null)

    try {
      await linkByUrlMutation.mutateAsync({ id: designId, url: linkUrl.trim() })
      setShowLinkInput(false)
      setLinkUrl('')
    } catch (err) {
      setLinkError((err as Error).message || 'Failed to link to Thangs')
    }
  }

  if (thangs) {
    // Linked state
    return (
      <div className="bg-bg-secondary rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ThangsIcon className="w-5 h-5 text-accent-primary" />
            <span className="font-medium text-text-primary">Thangs</span>
            <span className="text-xs px-2 py-0.5 rounded bg-accent-success/20 text-accent-success font-medium">
              Linked
            </span>
          </div>
        </div>

        <div className="space-y-3">
          {thangs.fetched_title && (
            <div>
              <span className="text-xs text-text-muted block mb-0.5">Title</span>
              <span className="text-text-primary text-sm">{thangs.fetched_title}</span>
            </div>
          )}
          {thangs.fetched_designer && (
            <div>
              <span className="text-xs text-text-muted block mb-0.5">Designer</span>
              <span className="text-text-primary text-sm">{thangs.fetched_designer}</span>
            </div>
          )}

          {thangs.last_fetched_at && (
            <div className="text-xs text-text-muted">
              Last fetched: {formatRelativeDate(thangs.last_fetched_at)}
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-2">
            <a
              href={thangs.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-accent-primary hover:underline"
            >
              View on Thangs
              <ExternalLinkIcon className="w-3.5 h-3.5" />
            </a>
          </div>

          <div className="flex flex-wrap gap-2 pt-2 border-t border-bg-tertiary">
            <button
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              className="text-xs px-3 py-1.5 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/80 transition-colors disabled:opacity-50"
            >
              {refreshMutation.isPending ? 'Refreshing...' : 'Refresh Metadata'}
            </button>
            <button
              onClick={() => setShowUnlinkConfirm(true)}
              disabled={unlinkMutation.isPending}
              className="text-xs px-3 py-1.5 rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors disabled:opacity-50"
            >
              Unlink
            </button>
          </div>

          {/* Unlink confirmation */}
          {showUnlinkConfirm && (
            <div className="mt-3 p-3 bg-bg-tertiary rounded-lg">
              <p className="text-sm text-text-secondary mb-3">
                Are you sure you want to unlink this design from Thangs?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleUnlink}
                  disabled={unlinkMutation.isPending}
                  className="text-xs px-3 py-1.5 rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
                >
                  {unlinkMutation.isPending ? 'Unlinking...' : 'Yes, Unlink'}
                </button>
                <button
                  onClick={() => setShowUnlinkConfirm(false)}
                  className="text-xs px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Not linked state
  return (
    <div className="bg-bg-secondary rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <ThangsIcon className="w-5 h-5 text-text-muted" />
        <span className="font-medium text-text-secondary">Thangs</span>
        <span className="text-xs px-2 py-0.5 rounded bg-bg-tertiary text-text-muted">
          Not Linked
        </span>
      </div>

      <p className="text-sm text-text-muted mb-4">
        Link this design to a Thangs model to fetch metadata and enable tracking.
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={onSearchThangs}
          className="text-sm px-3 py-1.5 rounded bg-accent-primary text-white hover:bg-accent-primary/80 transition-colors"
        >
          Search Thangs
        </button>
        <button
          onClick={() => setShowLinkInput(!showLinkInput)}
          className="text-sm px-3 py-1.5 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
        >
          Link by URL
        </button>
      </div>

      {/* Link by URL input */}
      {showLinkInput && (
        <div className="mt-3 space-y-2">
          <input
            type="url"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://thangs.com/designer/..."
            className="w-full px-3 py-2 bg-bg-tertiary rounded text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
          />
          {linkError && (
            <p className="text-xs text-accent-danger">{linkError}</p>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleLinkByUrl}
              disabled={!linkUrl.trim() || linkByUrlMutation.isPending}
              className="text-xs px-3 py-1.5 rounded bg-accent-primary text-white hover:bg-accent-primary/80 transition-colors disabled:opacity-50"
            >
              {linkByUrlMutation.isPending ? 'Linking...' : 'Link'}
            </button>
            <button
              onClick={() => {
                setShowLinkInput(false)
                setLinkUrl('')
                setLinkError(null)
              }}
              className="text-xs px-3 py-1.5 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

interface MetadataFieldProps {
  label: string
  value: string
  authority: MetadataAuthority
  isOverridden?: boolean
  onClearOverride?: () => void
}

function MetadataField({ label, value, authority, isOverridden, onClearOverride }: MetadataFieldProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <dt className="text-sm text-text-muted">{label}</dt>
        <MetadataSourceBadge authority={authority} />
        {isOverridden && <EditedBadge />}
      </div>
      <dd className="text-text-primary mt-1 flex items-center gap-2">
        <span>{value}</span>
        {isOverridden && onClearOverride && (
          <button
            onClick={onClearOverride}
            className="text-xs text-text-muted hover:text-accent-danger transition-colors"
            title="Reset to canonical value"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        )}
      </dd>
    </div>
  )
}

function DesignDetailSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-8 bg-bg-tertiary rounded w-1/3" />
      <div className="h-6 bg-bg-tertiary rounded w-1/4" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-bg-secondary rounded-lg p-6 space-y-4">
            <div className="h-4 bg-bg-tertiary rounded w-1/2" />
            <div className="h-4 bg-bg-tertiary rounded w-3/4" />
            <div className="h-4 bg-bg-tertiary rounded w-2/3" />
          </div>
        </div>
        <div className="space-y-6">
          <div className="bg-bg-secondary rounded-lg p-6 space-y-4">
            <div className="h-4 bg-bg-tertiary rounded w-1/2" />
            <div className="h-4 bg-bg-tertiary rounded w-3/4" />
          </div>
        </div>
      </div>
    </div>
  )
}

export function DesignDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: design, isLoading, error } = useDesign(id || '')
  const updateDesign = useUpdateDesign()
  const unmergeMutation = useUnmergeDesign()
  const [showThangsModal, setShowThangsModal] = useState(false)
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set())
  const [showUnmergeConfirm, setShowUnmergeConfirm] = useState(false)
  const [unmergeError, setUnmergeError] = useState<string | null>(null)

  const handleClearTitleOverride = async () => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { title_override: null } })
  }

  const handleClearDesignerOverride = async () => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { designer_override: null } })
  }

  const handleSearchThangs = () => {
    setShowThangsModal(true)
  }

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds((prev) => {
      const next = new Set(prev)
      if (next.has(sourceId)) {
        next.delete(sourceId)
      } else {
        next.add(sourceId)
      }
      return next
    })
  }

  const handleUnmerge = async () => {
    if (!design || selectedSourceIds.size === 0) return
    setUnmergeError(null)

    try {
      await unmergeMutation.mutateAsync({
        designId: design.id,
        sourceIds: Array.from(selectedSourceIds),
      })
      setShowUnmergeConfirm(false)
      setSelectedSourceIds(new Set())
    } catch (err) {
      setUnmergeError((err as Error).message || 'Failed to unmerge sources')
    }
  }

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
  const hasTitleOverride = design.title_override !== null
  const hasDesignerOverride = design.designer_override !== null

  // Determine the effective metadata authority for display
  const titleAuthority: MetadataAuthority = hasTitleOverride ? 'USER' : design.metadata_authority
  const designerAuthority: MetadataAuthority = hasDesignerOverride ? 'USER' : design.metadata_authority

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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-text-primary">
              {design.display_title}
            </h1>
            {hasTitleOverride && <EditedBadge />}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-text-secondary">
              by {design.display_designer}
            </p>
            {hasDesignerOverride && <EditedBadge />}
          </div>
        </div>
        <StatusBadge status={design.status} />
      </div>

      {/* Merged indicator */}
      {design.sources.length > 1 && (
        <div className="flex items-center gap-2 text-sm">
          <MergeIcon className="w-4 h-4 text-accent-primary" />
          <span className="text-text-secondary">
            Merged from <strong className="text-text-primary">{design.sources.length}</strong> sources
          </span>
        </div>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info with Provenance */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Details
            </h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <MetadataField
                label="Title"
                value={design.display_title}
                authority={titleAuthority}
                isOverridden={hasTitleOverride}
                onClearOverride={handleClearTitleOverride}
              />
              <MetadataField
                label="Designer"
                value={design.display_designer}
                authority={designerAuthority}
                isOverridden={hasDesignerOverride}
                onClearOverride={handleClearDesignerOverride}
              />
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
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-text-primary">
                  Primary Source
                </h2>
                {design.sources.length > 1 && (
                  <span className="text-xs px-2 py-1 rounded bg-accent-primary/20 text-accent-primary">
                    Preferred
                  </span>
                )}
              </div>
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
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-text-primary">
                  Other Sources ({design.sources.length - 1})
                </h2>
                {selectedSourceIds.size > 0 && (
                  <button
                    onClick={() => setShowUnmergeConfirm(true)}
                    className="text-sm px-3 py-1.5 rounded bg-accent-warning/20 text-accent-warning hover:bg-accent-warning/30 transition-colors"
                  >
                    Split Off Selected ({selectedSourceIds.size})
                  </button>
                )}
              </div>
              <div className="space-y-3">
                {design.sources
                  .filter((s) => s.id !== preferredSource?.id)
                  .map((source) => (
                    <div
                      key={source.id}
                      className="flex items-center gap-3 py-2 border-b border-bg-tertiary last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.has(source.id)}
                        onChange={() => toggleSourceSelection(source.id)}
                        className="w-4 h-4 rounded border-text-muted text-accent-primary focus:ring-accent-primary focus:ring-offset-0 focus:ring-offset-bg-secondary bg-bg-tertiary"
                      />
                      <div className="flex-1 min-w-0">
                        <span className="text-text-primary text-sm">
                          {source.channel.title}
                        </span>
                        {source.caption_snapshot && (
                          <p className="text-xs text-text-muted mt-0.5 truncate max-w-xs">
                            {source.caption_snapshot.slice(0, 80)}...
                          </p>
                        )}
                      </div>
                      <span className="text-sm text-text-muted">
                        {formatRelativeDate(source.created_at)}
                      </span>
                    </div>
                  ))}
              </div>

              {/* Unmerge Confirmation Dialog */}
              {showUnmergeConfirm && (
                <div className="mt-4 p-4 bg-bg-tertiary rounded-lg">
                  <p className="text-sm text-text-primary mb-3">
                    Split off {selectedSourceIds.size} source{selectedSourceIds.size !== 1 ? 's' : ''} into a new design?
                  </p>
                  <p className="text-xs text-text-muted mb-4">
                    This will create a new design with the selected sources.
                  </p>
                  {unmergeError && (
                    <p className="text-sm text-accent-danger mb-3">{unmergeError}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={handleUnmerge}
                      disabled={unmergeMutation.isPending}
                      className="text-sm px-3 py-1.5 rounded bg-accent-warning text-white hover:bg-accent-warning/80 transition-colors disabled:opacity-50"
                    >
                      {unmergeMutation.isPending ? 'Splitting...' : 'Split Off'}
                    </button>
                    <button
                      onClick={() => {
                        setShowUnmergeConfirm(false)
                        setUnmergeError(null)
                      }}
                      className="text-sm px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Download Section */}
          <DownloadSection
            designId={design.id}
            status={design.status}
          />

          {/* Thangs Section */}
          <ThangsSection
            designId={design.id}
            thangs={thangsLink || null}
            onSearchThangs={handleSearchThangs}
          />

          {/* Notes */}
          {design.notes && (
            <section className="bg-bg-secondary rounded-lg p-4">
              <h3 className="text-sm font-medium text-text-muted mb-2">Notes</h3>
              <p className="text-text-secondary text-sm whitespace-pre-wrap">
                {design.notes}
              </p>
            </section>
          )}

          {/* Metadata Info */}
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-muted mb-3">
              Metadata Info
            </h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between items-center">
                <dt className="text-text-muted">Authority</dt>
                <dd>
                  <MetadataSourceBadge authority={design.metadata_authority} />
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
                <dt className="text-text-muted">Last Updated</dt>
                <dd className="text-text-primary">
                  {formatRelativeDate(design.updated_at)}
                </dd>
              </div>
            </dl>
          </section>

          {/* Match Info (if Thangs linked) */}
          {thangsLink && (
            <section className="bg-bg-secondary rounded-lg p-4">
              <h3 className="text-sm font-medium text-text-muted mb-3">
                Match Info
              </h3>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-text-muted">Method</dt>
                  <dd className="text-text-primary capitalize">
                    {thangsLink.match_method.toLowerCase()}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-text-muted">Confidence</dt>
                  <dd className="text-text-primary">
                    {(thangsLink.confidence_score * 100).toFixed(0)}%
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-text-muted">Confirmed</dt>
                  <dd className="text-text-primary">
                    {thangsLink.is_user_confirmed ? 'Yes' : 'No'}
                  </dd>
                </div>
              </dl>
            </section>
          )}
        </div>
      </div>

      {/* Thangs Search Modal */}
      <ThangsSearchModal
        isOpen={showThangsModal}
        onClose={() => setShowThangsModal(false)}
        designId={design.id}
        designTitle={design.display_title}
      />
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

function ThangsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  )
}

function MergeIcon({ className }: { className?: string }) {
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
        d="M8 7h12m0 0l-4-4m4 4l-4 4M8 17h12m0 0l-4-4m4 4l-4 4M3 5v14"
      />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
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
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
}
