/**
 * Card component for displaying an import source
 */
import { useState } from 'react'
import type { ImportSource } from '@/types/import-source'
import { useTriggerSync } from '@/hooks/useImportSources'

interface ImportSourceCardProps {
  source: ImportSource
  onEdit: (source: ImportSource) => void
  onDelete: (id: string) => void
  onViewHistory: (id: string) => void
  isDeleting: boolean
}

export function ImportSourceCard({
  source,
  onEdit,
  onDelete,
  onViewHistory,
  isDeleting,
}: ImportSourceCardProps) {
  const [syncResult, setSyncResult] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  const triggerSync = useTriggerSync()

  const handleSync = async () => {
    setSyncResult(null)
    try {
      const result = await triggerSync.mutateAsync({ id: source.id })
      setSyncResult({
        type: 'success',
        message: result.message || `Sync complete: ${result.designs_detected} detected, ${result.designs_imported} imported`,
      })
      // Clear success message after 5 seconds
      setTimeout(() => setSyncResult(null), 5000)
    } catch (err) {
      setSyncResult({
        type: 'error',
        message: `Sync failed: ${(err as Error).message}`,
      })
    }
  }

  const getSourceIcon = () => {
    switch (source.source_type) {
      case 'GOOGLE_DRIVE':
        return <GoogleDriveIcon className="w-6 h-6" />
      case 'BULK_FOLDER':
        return <FolderIcon className="w-6 h-6" />
      case 'UPLOAD':
        return <UploadIcon className="w-6 h-6" />
      default:
        return <FolderIcon className="w-6 h-6" />
    }
  }

  const getSourceTypeLabel = () => {
    switch (source.source_type) {
      case 'GOOGLE_DRIVE':
        return 'Google Drive'
      case 'BULK_FOLDER':
        return 'Bulk Folder'
      case 'UPLOAD':
        return 'Upload'
      default:
        return source.source_type
    }
  }

  const getStatusBadge = () => {
    const statusStyles = {
      ACTIVE: 'bg-accent-success/20 text-accent-success',
      PAUSED: 'bg-text-muted/20 text-text-muted',
      ERROR: 'bg-accent-danger/20 text-accent-danger',
      PENDING: 'bg-accent-warning/20 text-accent-warning',
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${statusStyles[source.status]}`}>
        {source.status}
      </span>
    )
  }

  const getLastSyncText = () => {
    if (!source.last_sync_at) return 'Never synced'
    const date = new Date(source.last_sync_at)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} min ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  const getLocationText = () => {
    if (source.source_type === 'GOOGLE_DRIVE' && source.google_drive_url) {
      return source.google_drive_url
    }
    if (source.source_type === 'BULK_FOLDER' && source.folder_path) {
      return source.folder_path
    }
    return '-'
  }

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      {/* Main card content */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          {/* Left side - icon and info */}
          <div className="flex items-start gap-4 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-lg bg-bg-tertiary flex items-center justify-center text-text-secondary flex-shrink-0">
              {getSourceIcon()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-medium text-text-primary truncate">{source.name}</h3>
                <span className="text-xs text-text-muted bg-bg-tertiary px-2 py-0.5 rounded">
                  {getSourceTypeLabel()}
                </span>
              </div>
              <p className="text-sm text-text-secondary truncate mt-0.5" title={getLocationText()}>
                {getLocationText()}
              </p>
              <div className="flex items-center gap-4 mt-2 text-xs text-text-muted">
                <span>Last sync: {getLastSyncText()}</span>
                <span>{source.items_imported} designs imported</span>
                {source.profile && (
                  <span className="flex items-center gap-1">
                    <span>Profile:</span>
                    <span className="text-text-secondary">{source.profile.name}</span>
                    {source.profile.is_builtin && (
                      <span className="text-accent-primary text-[10px]">built-in</span>
                    )}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Right side - status and actions */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {getStatusBadge()}

            {/* Sync Now button */}
            <button
              onClick={handleSync}
              disabled={triggerSync.isPending || source.source_type === 'UPLOAD'}
              className="p-2 text-text-secondary hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Sync now"
              title={source.source_type === 'UPLOAD' ? 'Upload sources cannot be synced' : 'Sync now'}
            >
              {triggerSync.isPending ? (
                <SpinnerIcon className="w-5 h-5 animate-spin" />
              ) : (
                <RefreshIcon className="w-5 h-5" />
              )}
            </button>

            {/* View History button */}
            <button
              onClick={() => onViewHistory(source.id)}
              className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
              aria-label="View history"
              title="View import history"
            >
              <HistoryIcon className="w-5 h-5" />
            </button>

            {/* Edit button */}
            <button
              onClick={() => onEdit(source)}
              className="p-2 text-text-secondary hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors"
              aria-label="Edit source"
              title="Edit source"
            >
              <EditIcon className="w-5 h-5" />
            </button>

            {/* Delete button */}
            <button
              onClick={() => onDelete(source.id)}
              disabled={isDeleting}
              className="p-2 text-text-secondary hover:text-accent-danger hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50"
              aria-label="Delete source"
              title="Delete source"
            >
              <TrashIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Error message if last sync failed */}
        {source.status === 'ERROR' && source.last_sync_error && (
          <div className="mt-3 px-3 py-2 bg-accent-danger/10 border border-accent-danger/20 rounded text-sm text-accent-danger">
            {source.last_sync_error}
          </div>
        )}
      </div>

      {/* Sync result notification */}
      {syncResult && (
        <div
          className={`px-4 py-2 text-sm ${
            syncResult.type === 'success'
              ? 'bg-accent-success/20 text-accent-success'
              : 'bg-accent-danger/20 text-accent-danger'
          }`}
        >
          {syncResult.message}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function GoogleDriveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7.71 3.5L1.15 15l3.43 5.95L11.15 9.5 7.71 3.5zm2.85 0l6.57 11.43H22.7L16.14 3.5H10.56zm4.01 12.15L11.15 21h11.55l3.43-5.35H14.57z" />
    </svg>
  )
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
      />
    </svg>
  )
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
      />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  )
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
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

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" strokeWidth={2} strokeDasharray="60" strokeDashoffset="20" />
    </svg>
  )
}
