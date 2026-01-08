import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useDesign,
  useUnlinkFromThangs,
  useRefreshMetadata,
  useLinkToThangsByUrl,
  useUpdateDesign,
  useUnmergeDesign,
  useDeleteDesign,
} from '@/hooks/useDesigns'
import { useDesignPreviews, useSetPrimaryPreview } from '@/hooks/usePreviews'
import { useDesignTags } from '@/hooks/useTags'
import { useAiAnalyze, useAiStatus } from '@/hooks/useAi'
import {
  ThangsSearchModal,
  DownloadSection,
  PreviewGallery,
  PreviewGallerySkeleton,
  TagManager,
  DeleteConfirmModal,
} from '@/components/designs'
import type {
  DesignStatus,
  ExternalMetadata,
  MetadataAuthority,
  MulticolorStatus,
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

// Editable metadata field with inline editing
interface EditableMetadataFieldProps {
  label: string
  value: string
  canonicalValue: string
  authority: MetadataAuthority
  isOverridden?: boolean
  onSave: (value: string) => Promise<void>
  onClearOverride?: () => void
  isSaving?: boolean
  placeholder?: string
}

function EditableMetadataField({
  label,
  value,
  canonicalValue,
  authority,
  isOverridden,
  onSave,
  onClearOverride,
  isSaving,
  placeholder,
}: EditableMetadataFieldProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value)

  const handleStartEdit = () => {
    setEditValue(value)
    setIsEditing(true)
  }

  const handleSave = async () => {
    if (editValue.trim() !== value) {
      await onSave(editValue.trim())
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditValue(value)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  if (isEditing) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-1">
          <dt className="text-sm text-text-muted">{label}</dt>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 px-2 py-1 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
            placeholder={placeholder || canonicalValue}
            autoFocus
            disabled={isSaving}
          />
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="p-1 text-accent-success hover:bg-accent-success/20 rounded transition-colors disabled:opacity-50"
            title="Save"
          >
            <CheckIcon className="w-4 h-4" />
          </button>
          <button
            onClick={handleCancel}
            disabled={isSaving}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
            title="Cancel"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>
        {canonicalValue !== value && (
          <p className="text-xs text-text-muted mt-1">
            Original: {canonicalValue}
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <dt className="text-sm text-text-muted">{label}</dt>
        <MetadataSourceBadge authority={authority} />
        {isOverridden && <EditedBadge />}
      </div>
      <dd className="text-text-primary mt-1 flex items-center gap-2 group">
        <span>{value}</span>
        <button
          onClick={handleStartEdit}
          className="p-1 text-text-muted opacity-0 group-hover:opacity-100 hover:text-accent-primary hover:bg-bg-tertiary rounded transition-all"
          title={`Edit ${label.toLowerCase()}`}
        >
          <PencilIcon className="w-3.5 h-3.5" />
        </button>
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

// Editable notes section
interface EditableNotesSectionProps {
  notes: string | null
  onSave: (notes: string | null) => Promise<void>
  isSaving?: boolean
}

function EditableNotesSection({ notes, onSave, isSaving }: EditableNotesSectionProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(notes || '')

  const handleStartEdit = () => {
    setEditValue(notes || '')
    setIsEditing(true)
  }

  const handleSave = async () => {
    const newNotes = editValue.trim() || null
    if (newNotes !== notes) {
      await onSave(newNotes)
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditValue(notes || '')
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <section className="bg-bg-secondary rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-text-muted">Notes</h3>
          <div className="flex items-center gap-1">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="p-1 text-accent-success hover:bg-accent-success/20 rounded transition-colors disabled:opacity-50"
              title="Save"
            >
              <CheckIcon className="w-4 h-4" />
            </button>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="p-1 text-text-muted hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
              title="Cancel"
            >
              <CloseIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="w-full px-3 py-2 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary resize-none"
          rows={4}
          placeholder="Add notes about this design..."
          autoFocus
          disabled={isSaving}
        />
      </section>
    )
  }

  return (
    <section className="bg-bg-secondary rounded-lg p-4 group">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-muted">Notes</h3>
        <button
          onClick={handleStartEdit}
          className="p-1 text-text-muted opacity-0 group-hover:opacity-100 hover:text-accent-primary hover:bg-bg-tertiary rounded transition-all"
          title="Edit notes"
        >
          <PencilIcon className="w-3.5 h-3.5" />
        </button>
      </div>
      {notes ? (
        <p className="text-text-secondary text-sm whitespace-pre-wrap">
          {notes}
        </p>
      ) : (
        <p className="text-text-muted text-sm italic">
          No notes yet. Click to add.
        </p>
      )}
    </section>
  )
}

// Multicolor status selector
interface MulticolorSelectorProps {
  displayValue: MulticolorStatus
  hasOverride: boolean
  onSave: (value: MulticolorStatus | null) => Promise<void>
  onClear: () => Promise<void>
  isSaving?: boolean
}

function MulticolorSelector({
  displayValue,
  hasOverride,
  onSave,
  onClear,
  isSaving,
}: MulticolorSelectorProps) {
  const [isEditing, setIsEditing] = useState(false)

  const options: { value: MulticolorStatus; label: string; className: string }[] = [
    { value: 'UNKNOWN', label: 'Unknown', className: 'text-text-muted' },
    { value: 'SINGLE', label: 'Single Color', className: 'text-text-secondary' },
    { value: 'MULTI', label: 'Multicolor', className: 'text-purple-400' },
  ]

  const handleChange = async (newValue: MulticolorStatus) => {
    if (newValue !== displayValue) {
      await onSave(newValue)
    }
    setIsEditing(false)
  }

  const currentOption = options.find((o) => o.value === displayValue) || options[0]

  if (isEditing) {
    return (
      <div>
        <dt className="text-sm text-text-muted mb-1">Color Type</dt>
        <div className="flex items-center gap-2">
          <select
            value={displayValue}
            onChange={(e) => handleChange(e.target.value as MulticolorStatus)}
            disabled={isSaving}
            className="flex-1 px-2 py-1 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
            autoFocus
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => setIsEditing(false)}
            className="p-1 text-text-muted hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
            title="Cancel"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <dt className="text-sm text-text-muted mb-1 flex items-center gap-2">
        Color Type
        {hasOverride && <EditedBadge />}
      </dt>
      <dd className={`mt-1 flex items-center gap-2 group ${currentOption.className}`}>
        <span>{currentOption.label}</span>
        {displayValue === 'MULTI' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-medium">
            MMU
          </span>
        )}
        <button
          onClick={() => setIsEditing(true)}
          className="p-1 text-text-muted opacity-0 group-hover:opacity-100 hover:text-accent-primary hover:bg-bg-tertiary rounded transition-all"
          title="Edit color type"
        >
          <PencilIcon className="w-3.5 h-3.5" />
        </button>
        {hasOverride && (
          <button
            onClick={onClear}
            className="text-xs text-text-muted hover:text-accent-danger transition-colors"
            title="Reset to detected value"
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
  const navigate = useNavigate()
  const { data: design, isLoading, error } = useDesign(id || '')
  const { data: previewsData, isLoading: previewsLoading } = useDesignPreviews(id || '')
  const { data: tagsData } = useDesignTags(id || '')
  const updateDesign = useUpdateDesign()
  const unmergeMutation = useUnmergeDesign()
  const deleteMutation = useDeleteDesign()
  const setPrimaryMutation = useSetPrimaryPreview()
  const { data: aiStatus } = useAiStatus()
  const aiAnalyzeMutation = useAiAnalyze()
  const [showThangsModal, setShowThangsModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set())
  const [showUnmergeConfirm, setShowUnmergeConfirm] = useState(false)
  const [unmergeError, setUnmergeError] = useState<string | null>(null)

  // Navigate back to designs list, preserving filters via browser history
  const handleBack = useCallback(() => {
    // Check if we can go back in history (came from designs list)
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      // Fallback if no history (direct link to this page)
      navigate('/designs')
    }
  }, [navigate])

  const handleSetPrimary = async (previewId: string) => {
    try {
      await setPrimaryMutation.mutateAsync(previewId)
    } catch (err) {
      console.error('Failed to set primary preview:', err)
    }
  }

  const handleClearTitleOverride = async () => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { title_override: null } })
  }

  const handleClearDesignerOverride = async () => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { designer_override: null } })
  }

  const handleSaveTitle = async (value: string) => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { title_override: value } })
  }

  const handleSaveDesigner = async (value: string) => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { designer_override: value } })
  }

  const handleSaveNotes = async (value: string | null) => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { notes: value } })
  }

  const handleSaveMulticolor = async (value: MulticolorStatus | null) => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { multicolor_override: value } })
  }

  const handleClearMulticolorOverride = async () => {
    if (!design) return
    await updateDesign.mutateAsync({ id: design.id, data: { multicolor_override: null } })
  }

  const handleSearchThangs = () => {
    setShowThangsModal(true)
  }

  const handleDelete = async (deleteFiles: boolean) => {
    if (!design) return
    try {
      await deleteMutation.mutateAsync({ id: design.id, deleteFiles })
      // Navigate back to designs list after successful deletion
      navigate('/designs')
    } catch (err) {
      // Re-throw to let the modal display the error
      throw err
    }
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
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </button>
        <DesignDetailSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </button>
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
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back to Designs
        </button>
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
      {/* Back Button */}
      <button
        onClick={handleBack}
        className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
      >
        <BackIcon className="w-4 h-4" />
        Back to Designs
      </button>

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
        <div className="flex items-center gap-3">
          <StatusBadge status={design.status} />
          <button
            onClick={() => setShowDeleteModal(true)}
            className="p-2 rounded text-text-muted hover:text-accent-danger hover:bg-accent-danger/10 transition-colors"
            title="Delete design"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
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
          {/* Preview Gallery */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Preview Images
              {previewsData && previewsData.total > 0 && (
                <span className="text-sm font-normal text-text-muted ml-2">
                  ({previewsData.total})
                </span>
              )}
            </h2>
            {previewsLoading ? (
              <PreviewGallerySkeleton />
            ) : (
              <PreviewGallery
                previews={previewsData?.items || []}
                onSetPrimary={handleSetPrimary}
                isSettingPrimary={setPrimaryMutation.isPending}
              />
            )}
          </section>

          {/* Tags */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Tags
              {tagsData && tagsData.length > 0 && (
                <span className="text-sm font-normal text-text-muted ml-2">
                  ({tagsData.length})
                </span>
              )}
            </h2>
            <TagManager
              designId={design.id}
              tags={tagsData || []}
              maxTags={20}
            />
          </section>

          {/* Basic Info with Provenance */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Details
            </h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <EditableMetadataField
                label="Title"
                value={design.display_title}
                canonicalValue={design.canonical_title}
                authority={titleAuthority}
                isOverridden={hasTitleOverride}
                onSave={handleSaveTitle}
                onClearOverride={handleClearTitleOverride}
                isSaving={updateDesign.isPending}
                placeholder="Enter title..."
              />
              <EditableMetadataField
                label="Designer"
                value={design.display_designer}
                canonicalValue={design.canonical_designer}
                authority={designerAuthority}
                isOverridden={hasDesignerOverride}
                onSave={handleSaveDesigner}
                onClearOverride={handleClearDesignerOverride}
                isSaving={updateDesign.isPending}
                placeholder="Enter designer..."
              />
              <div>
                <dt className="text-sm text-text-muted">File Types</dt>
                <dd className="text-text-primary mt-1">
                  {(() => {
                    if (!design.primary_file_types) return 'Unknown'
                    try {
                      const types = JSON.parse(design.primary_file_types)
                      return Array.isArray(types) ? types.join(', ') : design.primary_file_types
                    } catch {
                      return design.primary_file_types
                    }
                  })()}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Total Size</dt>
                <dd className="text-text-primary mt-1">
                  {formatFileSize(design.total_size_bytes)}
                </dd>
              </div>
              <MulticolorSelector
                displayValue={design.display_multicolor}
                hasOverride={design.multicolor_override !== null}
                onSave={handleSaveMulticolor}
                onClear={handleClearMulticolorOverride}
                isSaving={updateDesign.isPending}
              />
              <div>
                <dt className="text-sm text-text-muted">Added</dt>
                <dd className="text-text-primary mt-1">
                  {formatDate(design.created_at)}
                </dd>
              </div>
            </dl>
          </section>

          {/* Source Info - DEC-042: Improved sources display */}
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
                <div className="flex items-center gap-3">
                  <TelegramIcon className="w-5 h-5 text-blue-400" />
                  <div>
                    <dt className="text-sm text-text-muted">Source</dt>
                    <dd className="text-text-primary mt-0.5 flex items-center gap-2">
                      <span>{preferredSource.channel.title}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-medium">
                        Telegram
                      </span>
                    </dd>
                  </div>
                </div>
                <div>
                  <dt className="text-sm text-text-muted">Discovered</dt>
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

          {/* Additional Sources - DEC-042: Expandable with split buttons */}
          {design.sources.length > 1 && (
            <SourcesSection
              sources={design.sources}
              preferredSourceId={preferredSource?.id}
              selectedSourceIds={selectedSourceIds}
              onToggleSelection={toggleSourceSelection}
              onSplitSelected={() => setShowUnmergeConfirm(true)}
            >
              <div className="space-y-3">
                {design.sources
                  .filter((s) => s.id !== preferredSource?.id)
                  .map((source) => (
                    <div
                      key={source.id}
                      className="flex items-center gap-3 py-3 border-b border-bg-tertiary last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.has(source.id)}
                        onChange={() => toggleSourceSelection(source.id)}
                        className="w-4 h-4 rounded border-text-muted text-accent-primary focus:ring-accent-primary focus:ring-offset-0 focus:ring-offset-bg-secondary bg-bg-tertiary"
                      />
                      <TelegramIcon className="w-4 h-4 text-blue-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-text-primary text-sm font-medium">
                            {source.channel.title}
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            Telegram
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-text-muted">
                            Discovered {formatRelativeDate(source.created_at)}
                          </span>
                        </div>
                        {source.caption_snapshot && (
                          <p className="text-xs text-text-muted mt-1 truncate max-w-md">
                            {source.caption_snapshot.slice(0, 100)}...
                          </p>
                        )}
                      </div>
                      {/* DEC-042: Individual split button per source */}
                      <button
                        onClick={() => {
                          setSelectedSourceIds(new Set([source.id]))
                          setShowUnmergeConfirm(true)
                        }}
                        className="text-xs px-2 py-1 rounded bg-bg-tertiary text-text-muted hover:text-accent-warning hover:bg-accent-warning/10 transition-colors flex items-center gap-1"
                        title="Split this source into a new design"
                      >
                        <SplitIcon className="w-3.5 h-3.5" />
                        Split
                      </button>
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
            </SourcesSection>
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

          {/* AI Analysis Section */}
          {aiStatus?.enabled && (
            <section className="bg-bg-secondary rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <AiSparklesIcon className="w-5 h-5 text-purple-400" />
                <h3 className="text-sm font-medium text-text-muted">AI Analysis</h3>
              </div>
              <p className="text-sm text-text-secondary mb-3">
                Use AI to automatically generate tags based on design images and metadata.
              </p>
              <button
                onClick={() => aiAnalyzeMutation.mutate({ designId: design.id })}
                disabled={aiAnalyzeMutation.isPending}
                className="w-full px-3 py-2 text-sm rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <AiSparklesIcon className="w-4 h-4" />
                {aiAnalyzeMutation.isPending ? 'Analyzing...' : 'Analyze with AI'}
              </button>
              {aiAnalyzeMutation.isSuccess && (
                <p className="mt-2 text-xs text-accent-success">
                  Analysis queued successfully. Tags will appear shortly.
                </p>
              )}
              {aiAnalyzeMutation.isError && (
                <p className="mt-2 text-xs text-accent-danger">
                  Failed to queue analysis. Please try again.
                </p>
              )}
            </section>
          )}

          {/* Notes */}
          <EditableNotesSection
            notes={design.notes}
            onSave={handleSaveNotes}
            isSaving={updateDesign.isPending}
          />

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

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        designTitle={design.display_title}
        isPending={deleteMutation.isPending}
        hasFiles={design.status === 'ORGANIZED' || design.status === 'DOWNLOADED'}
      />
    </div>
  )
}

// SourcesSection - Expandable container for duplicate sources (DEC-042)
interface SourcesSectionProps {
  sources: { id: string }[]
  preferredSourceId: string | undefined
  selectedSourceIds: Set<string>
  onToggleSelection: (id: string) => void
  onSplitSelected: () => void
  children: React.ReactNode
}

function SourcesSection({
  sources,
  preferredSourceId,
  selectedSourceIds,
  onSplitSelected,
  children,
}: SourcesSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const otherSourcesCount = sources.filter((s) => s.id !== preferredSourceId).length

  return (
    <section className="bg-bg-secondary rounded-lg p-6">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-medium text-text-primary">
            Other Sources
          </h2>
          <span className="text-xs px-2 py-0.5 rounded bg-accent-primary/20 text-accent-primary font-medium">
            {otherSourcesCount}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {selectedSourceIds.size > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onSplitSelected()
              }}
              className="text-sm px-3 py-1.5 rounded bg-accent-warning/20 text-accent-warning hover:bg-accent-warning/30 transition-colors"
            >
              Split Off Selected ({selectedSourceIds.size})
            </button>
          )}
          <ChevronDownIcon
            className={`w-5 h-5 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>
      {isExpanded && children}
    </section>
  )
}

// Icon Components

function ChevronDownIcon({ className }: { className?: string }) {
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
        d="M19 9l-7 7-7-7"
      />
    </svg>
  )
}

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  )
}

function SplitIcon({ className }: { className?: string }) {
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
        d="M8 7h12M8 17h12M3 12h18M3 12l4-4M3 12l4 4"
      />
    </svg>
  )
}

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

function CheckIcon({ className }: { className?: string }) {
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
        d="M5 13l4 4L19 7"
      />
    </svg>
  )
}

function PencilIcon({ className }: { className?: string }) {
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
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
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
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}

function AiSparklesIcon({ className }: { className?: string }) {
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
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
      />
    </svg>
  )
}
