/**
 * Card component for displaying an import profile
 */
import type { ImportProfile } from '@/types/import-source'

interface ImportProfileCardProps {
  profile: ImportProfile
  usageCount?: number
  onView: (profile: ImportProfile) => void
  onEdit: (profile: ImportProfile) => void
  onDuplicate: (profile: ImportProfile) => void
  onDelete: (profile: ImportProfile) => void
  isDeleting: boolean
}

export function ImportProfileCard({
  profile,
  usageCount = 0,
  onView,
  onEdit,
  onDuplicate,
  onDelete,
  isDeleting,
}: ImportProfileCardProps) {
  return (
    <div className="bg-bg-secondary rounded-lg p-4">
      <div className="flex items-start justify-between gap-4">
        {/* Left side - info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium text-text-primary">{profile.name}</h3>
            {profile.is_builtin ? (
              <span className="text-xs bg-accent-primary/20 text-accent-primary px-2 py-0.5 rounded flex items-center gap-1">
                <LockIcon className="w-3 h-3" />
                Built-in
              </span>
            ) : (
              <span className="text-xs bg-bg-tertiary text-text-muted px-2 py-0.5 rounded">
                Custom
              </span>
            )}
          </div>
          {profile.description && (
            <p className="text-sm text-text-secondary mt-1">{profile.description}</p>
          )}
          <div className="flex items-center gap-4 mt-2 text-xs text-text-muted">
            <span>Used by: {usageCount} source{usageCount !== 1 ? 's' : ''}</span>
            <span>Structure: {profile.config.detection.structure}</span>
            <span>
              Extensions: {profile.config.detection.model_extensions.slice(0, 3).join(', ')}
              {profile.config.detection.model_extensions.length > 3 && '...'}
            </span>
          </div>
        </div>

        {/* Right side - actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => onView(profile)}
            className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
            aria-label="View profile"
            title="View details"
          >
            <EyeIcon className="w-5 h-5" />
          </button>

          {!profile.is_builtin && (
            <button
              onClick={() => onEdit(profile)}
              className="p-2 text-text-secondary hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors"
              aria-label="Edit profile"
              title="Edit profile"
            >
              <EditIcon className="w-5 h-5" />
            </button>
          )}

          <button
            onClick={() => onDuplicate(profile)}
            className="p-2 text-text-secondary hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors"
            aria-label="Duplicate profile"
            title="Duplicate profile"
          >
            <DuplicateIcon className="w-5 h-5" />
          </button>

          {!profile.is_builtin && (
            <button
              onClick={() => onDelete(profile)}
              disabled={isDeleting || usageCount > 0}
              className="p-2 text-text-secondary hover:text-accent-danger hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Delete profile"
              title={usageCount > 0 ? 'Cannot delete: profile in use' : 'Delete profile'}
            >
              <TrashIcon className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Skeleton loader
export function ImportProfileCardSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <div className="h-5 w-32 bg-bg-tertiary rounded" />
            <div className="h-4 w-16 bg-bg-tertiary rounded" />
          </div>
          <div className="h-4 w-64 bg-bg-tertiary rounded mt-2" />
          <div className="flex items-center gap-4 mt-2">
            <div className="h-3 w-24 bg-bg-tertiary rounded" />
            <div className="h-3 w-24 bg-bg-tertiary rounded" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function LockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
      />
    </svg>
  )
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
      />
    </svg>
  )
}

function EditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
      />
    </svg>
  )
}

function DuplicateIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
