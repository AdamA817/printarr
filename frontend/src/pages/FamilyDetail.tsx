import { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  useFamily,
  useUpdateFamily,
  useDissolveFamily,
  useRemoveDesignFromFamily,
} from '@/hooks/useFamilies'
import type { FamilyDetectionMethod } from '@/types/family'
import type { DesignStatus } from '@/types/design'

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

const detectionMethodLabels: Record<FamilyDetectionMethod, string> = {
  NAME_PATTERN: 'Name Pattern',
  FILE_HASH_OVERLAP: 'File Hash Overlap',
  AI_DETECTED: 'AI Detected',
  MANUAL: 'Manual',
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

function StatusBadge({ status }: { status: string }) {
  const designStatus = status as DesignStatus
  const colors = statusColors[designStatus] || 'bg-text-muted text-text-primary'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {status}
    </span>
  )
}

function FamilyDetailSkeleton() {
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

// Editable field component
interface EditableFieldProps {
  label: string
  value: string
  originalValue: string
  isOverridden: boolean
  onSave: (value: string) => Promise<void>
  onClear: () => Promise<void>
  isSaving?: boolean
  placeholder?: string
}

function EditableField({
  label,
  value,
  originalValue,
  isOverridden,
  onSave,
  onClear,
  isSaving,
  placeholder,
}: EditableFieldProps) {
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
        <dt className="text-sm text-text-muted mb-1">{label}</dt>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 px-2 py-1 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
            placeholder={placeholder || originalValue}
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
        {originalValue !== value && (
          <p className="text-xs text-text-muted mt-1">
            Original: {originalValue}
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      <dt className="text-sm text-text-muted mb-1 flex items-center gap-2">
        {label}
        {isOverridden && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-warning/20 text-accent-warning font-medium">
            edited
          </span>
        )}
      </dt>
      <dd className="text-text-primary mt-1 flex items-center gap-2 group">
        <span>{value}</span>
        <button
          onClick={handleStartEdit}
          className="p-1 text-text-muted opacity-0 group-hover:opacity-100 hover:text-accent-primary hover:bg-bg-tertiary rounded transition-all"
          title={`Edit ${label.toLowerCase()}`}
        >
          <PencilIcon className="w-3.5 h-3.5" />
        </button>
        {isOverridden && (
          <button
            onClick={onClear}
            className="text-xs text-text-muted hover:text-accent-danger transition-colors"
            title="Reset to original"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        )}
      </dd>
    </div>
  )
}

export function FamilyDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: family, isLoading, error } = useFamily(id)
  const updateFamily = useUpdateFamily()
  const dissolveMutation = useDissolveFamily()
  const removeDesignMutation = useRemoveDesignFromFamily()
  const [showDissolveConfirm, setShowDissolveConfirm] = useState(false)
  const [selectedDesignIds, setSelectedDesignIds] = useState<Set<string>>(new Set())
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false)
  const [removeError, setRemoveError] = useState<string | null>(null)

  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/designs')
    }
  }, [navigate])

  const handleSaveName = async (value: string) => {
    if (!family) return
    await updateFamily.mutateAsync({
      id: family.id,
      data: { name_override: value || null },
    })
  }

  const handleClearNameOverride = async () => {
    if (!family) return
    await updateFamily.mutateAsync({
      id: family.id,
      data: { name_override: null },
    })
  }

  const handleSaveDesigner = async (value: string) => {
    if (!family) return
    await updateFamily.mutateAsync({
      id: family.id,
      data: { designer_override: value || null },
    })
  }

  const handleClearDesignerOverride = async () => {
    if (!family) return
    await updateFamily.mutateAsync({
      id: family.id,
      data: { designer_override: null },
    })
  }

  const handleSaveDescription = async (value: string) => {
    if (!family) return
    await updateFamily.mutateAsync({
      id: family.id,
      data: { description: value || null },
    })
  }

  const handleDissolve = async () => {
    if (!family) return
    try {
      await dissolveMutation.mutateAsync(family.id)
      navigate('/designs')
    } catch (err) {
      console.error('Failed to dissolve family:', err)
    }
  }

  const toggleDesignSelection = (designId: string) => {
    setSelectedDesignIds((prev) => {
      const next = new Set(prev)
      if (next.has(designId)) {
        next.delete(designId)
      } else {
        next.add(designId)
      }
      return next
    })
  }

  const handleRemoveSelected = async () => {
    if (!family || selectedDesignIds.size === 0) return
    setRemoveError(null)

    try {
      for (const designId of selectedDesignIds) {
        await removeDesignMutation.mutateAsync({
          familyId: family.id,
          designId,
        })
      }
      setSelectedDesignIds(new Set())
      setShowRemoveConfirm(false)
    } catch (err) {
      setRemoveError((err as Error).message || 'Failed to remove designs')
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
          Back
        </button>
        <FamilyDetailSkeleton />
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
          Back
        </button>
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load family: {(error as Error).message}
          </p>
        </div>
      </div>
    )
  }

  if (!family) {
    return (
      <div className="space-y-6">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <BackIcon className="w-4 h-4" />
          Back
        </button>
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <p className="text-text-secondary">Family not found</p>
        </div>
      </div>
    )
  }

  const hasNameOverride = family.name_override !== null
  const hasDesignerOverride = family.designer_override !== null

  return (
    <div className="space-y-6">
      {/* Navigation */}
      <button
        onClick={handleBack}
        className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
      >
        <BackIcon className="w-4 h-4" />
        Back
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <FamilyIcon className="w-8 h-8 text-accent-primary" />
            <h1 className="text-2xl font-bold text-text-primary">
              {family.display_name}
            </h1>
            {hasNameOverride && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-warning/20 text-accent-warning font-medium">
                edited
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 ml-11">
            <p className="text-text-secondary">by {family.display_designer}</p>
            {hasDesignerOverride && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-warning/20 text-accent-warning font-medium">
                edited
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-1 rounded text-sm font-medium bg-accent-primary/20 text-accent-primary">
            {family.variant_count} variant{family.variant_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Variants */}
        <div className="lg:col-span-2 space-y-6">
          {/* Variants List */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-text-primary">
                Variants
              </h2>
              {selectedDesignIds.size > 0 && (
                <button
                  onClick={() => setShowRemoveConfirm(true)}
                  className="text-sm px-3 py-1.5 rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors"
                >
                  Remove Selected ({selectedDesignIds.size})
                </button>
              )}
            </div>

            {/* Remove Confirmation */}
            {showRemoveConfirm && (
              <div className="mb-4 p-4 bg-bg-tertiary rounded-lg">
                <p className="text-sm text-text-primary mb-3">
                  Remove {selectedDesignIds.size} design{selectedDesignIds.size !== 1 ? 's' : ''} from this family?
                </p>
                <p className="text-xs text-text-muted mb-4">
                  The designs will be ungrouped and become standalone.
                </p>
                {removeError && (
                  <p className="text-sm text-accent-danger mb-3">{removeError}</p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={handleRemoveSelected}
                    disabled={removeDesignMutation.isPending}
                    className="text-sm px-3 py-1.5 rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
                  >
                    {removeDesignMutation.isPending ? 'Removing...' : 'Remove'}
                  </button>
                  <button
                    onClick={() => {
                      setShowRemoveConfirm(false)
                      setRemoveError(null)
                    }}
                    className="text-sm px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {family.designs.map((design) => (
                <div
                  key={design.id}
                  className="flex items-center gap-3 p-3 bg-bg-tertiary rounded-lg hover:bg-bg-tertiary/80 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedDesignIds.has(design.id)}
                    onChange={() => toggleDesignSelection(design.id)}
                    className="w-4 h-4 rounded border-text-muted text-accent-primary focus:ring-accent-primary focus:ring-offset-0 focus:ring-offset-bg-tertiary bg-bg-secondary"
                  />
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/designs/${design.id}`}
                      className="text-text-primary font-medium hover:text-accent-primary transition-colors block truncate"
                    >
                      {design.canonical_title}
                    </Link>
                    <div className="flex items-center gap-2 mt-1">
                      {design.variant_name && (
                        <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                          {design.variant_name}
                        </span>
                      )}
                      <span className="text-xs text-text-muted">
                        by {design.canonical_designer}
                      </span>
                    </div>
                  </div>
                  <StatusBadge status={design.status} />
                </div>
              ))}

              {family.designs.length === 0 && (
                <p className="text-text-muted text-center py-4">
                  No variants in this family
                </p>
              )}
            </div>
          </section>

          {/* Tags */}
          {family.tags.length > 0 && (
            <section className="bg-bg-secondary rounded-lg p-6">
              <h2 className="text-lg font-medium text-text-primary mb-4">
                Aggregated Tags
              </h2>
              <div className="flex flex-wrap gap-2">
                {family.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="px-2 py-1 rounded text-sm bg-bg-tertiary text-text-secondary"
                  >
                    {tag.name}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right Column - Details */}
        <div className="space-y-6">
          {/* Family Details */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <h2 className="text-lg font-medium text-text-primary mb-4">
              Details
            </h2>
            <dl className="space-y-4">
              <EditableField
                label="Name"
                value={family.display_name}
                originalValue={family.canonical_name}
                isOverridden={hasNameOverride}
                onSave={handleSaveName}
                onClear={handleClearNameOverride}
                isSaving={updateFamily.isPending}
              />
              <EditableField
                label="Designer"
                value={family.display_designer}
                originalValue={family.canonical_designer}
                isOverridden={hasDesignerOverride}
                onSave={handleSaveDesigner}
                onClear={handleClearDesignerOverride}
                isSaving={updateFamily.isPending}
              />
              <div>
                <dt className="text-sm text-text-muted">Detection Method</dt>
                <dd className="text-text-primary mt-1 flex items-center gap-2">
                  <span>{detectionMethodLabels[family.detection_method]}</span>
                  {family.detection_confidence !== null && (
                    <span className="text-xs px-2 py-0.5 rounded bg-bg-tertiary text-text-muted">
                      {(family.detection_confidence * 100).toFixed(0)}% confidence
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Created</dt>
                <dd className="text-text-primary mt-1">
                  {formatDate(family.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-text-muted">Last Updated</dt>
                <dd className="text-text-primary mt-1">
                  {formatRelativeDate(family.updated_at)}
                </dd>
              </div>
            </dl>
          </section>

          {/* Description */}
          <section className="bg-bg-secondary rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-text-muted">Description</h3>
            </div>
            <EditableDescription
              value={family.description}
              onSave={handleSaveDescription}
              isSaving={updateFamily.isPending}
            />
          </section>

          {/* Danger Zone */}
          <section className="bg-bg-secondary rounded-lg p-6 border border-accent-danger/30">
            <h3 className="text-sm font-medium text-accent-danger mb-4">
              Danger Zone
            </h3>
            <p className="text-sm text-text-muted mb-4">
              Dissolving this family will remove all designs from the group. The designs themselves will not be deleted.
            </p>
            {showDissolveConfirm ? (
              <div className="space-y-3">
                <p className="text-sm text-text-primary">
                  Are you sure? This will ungroup all {family.variant_count} variant{family.variant_count !== 1 ? 's' : ''}.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={handleDissolve}
                    disabled={dissolveMutation.isPending}
                    className="px-3 py-1.5 rounded text-sm bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
                  >
                    {dissolveMutation.isPending ? 'Dissolving...' : 'Yes, Dissolve'}
                  </button>
                  <button
                    onClick={() => setShowDissolveConfirm(false)}
                    className="px-3 py-1.5 rounded text-sm bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowDissolveConfirm(true)}
                className="px-3 py-1.5 rounded text-sm bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors"
              >
                Dissolve Family
              </button>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

// Editable description component
interface EditableDescriptionProps {
  value: string | null
  onSave: (value: string) => Promise<void>
  isSaving?: boolean
}

function EditableDescription({ value, onSave, isSaving }: EditableDescriptionProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value || '')

  const handleStartEdit = () => {
    setEditValue(value || '')
    setIsEditing(true)
  }

  const handleSave = async () => {
    await onSave(editValue.trim())
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditValue(value || '')
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="w-full px-3 py-2 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary resize-none"
          rows={4}
          placeholder="Add a description..."
          autoFocus
          disabled={isSaving}
        />
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="text-xs px-3 py-1.5 rounded bg-accent-primary text-white hover:bg-accent-primary/80 transition-colors disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
          <button
            onClick={handleCancel}
            className="text-xs px-3 py-1.5 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      {value ? (
        <p
          onClick={handleStartEdit}
          className="text-text-secondary text-sm whitespace-pre-wrap cursor-pointer hover:text-text-primary transition-colors"
        >
          {value}
        </p>
      ) : (
        <p
          onClick={handleStartEdit}
          className="text-text-muted text-sm italic cursor-pointer hover:text-text-secondary transition-colors"
        >
          Click to add a description...
        </p>
      )}
    </div>
  )
}

// Icon Components
function BackIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
  )
}

function FamilyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
    </svg>
  )
}
