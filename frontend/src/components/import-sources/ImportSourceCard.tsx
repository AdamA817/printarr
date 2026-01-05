/**
 * Card component for displaying an import source with expandable folder list
 */
import { useState } from 'react'
import type { ImportSource, ImportSourceFolderSummary } from '@/types/import-source'
import { useTriggerSync, useSyncFolder, useUpdateFolder } from '@/hooks/useImportSources'

interface ImportSourceCardProps {
  source: ImportSource
  onEdit: (source: ImportSource) => void
  onDelete: (id: string) => void
  onViewHistory: (id: string) => void
  onAddFolder?: (sourceId: string) => void
  isDeleting: boolean
}

export function ImportSourceCard({
  source,
  onEdit,
  onDelete,
  onViewHistory,
  onAddFolder,
  isDeleting,
}: ImportSourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [syncResult, setSyncResult] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  const triggerSync = useTriggerSync()
  const syncFolder = useSyncFolder()
  const updateFolder = useUpdateFolder()

  const handleSync = async () => {
    setSyncResult(null)
    try {
      const result = await triggerSync.mutateAsync({
        id: source.id,
        request: { auto_import: true },
      })
      setSyncResult({
        type: 'success',
        message: result.message || `Sync complete: ${result.designs_detected} detected, ${result.designs_imported} imported`,
      })
      setTimeout(() => setSyncResult(null), 5000)
    } catch (err) {
      setSyncResult({
        type: 'error',
        message: `Sync failed: ${(err as Error).message}`,
      })
    }
  }

  const handleFolderSync = async (folderId: string) => {
    try {
      await syncFolder.mutateAsync({
        sourceId: source.id,
        folderId,
        request: { auto_import: true },
      })
    } catch (err) {
      console.error('Folder sync failed:', err)
    }
  }

  const handleToggleFolderEnabled = async (folder: ImportSourceFolderSummary) => {
    try {
      await updateFolder.mutateAsync({
        sourceId: source.id,
        folderId: folder.id,
        data: { enabled: !folder.enabled },
      })
    } catch (err) {
      console.error('Toggle folder failed:', err)
    }
  }

  const isSyncing = triggerSync.isPending
  const hasFolders = source.folders && source.folders.length > 0
  // Allow expanding for any source that can have multiple folders (even if currently empty)
  const canHaveMultipleFolders = source.source_type === 'GOOGLE_DRIVE' || source.source_type === 'BULK_FOLDER'

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
    if (isSyncing) {
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-accent-primary/20 text-accent-primary flex items-center gap-1">
          <SpinnerIcon className="w-3 h-3 animate-spin" />
          SYNCING
        </span>
      )
    }

    const statusStyles: Record<string, string> = {
      ACTIVE: 'bg-accent-success/20 text-accent-success',
      PAUSED: 'bg-text-muted/20 text-text-muted',
      ERROR: 'bg-accent-danger/20 text-accent-danger',
      PENDING: 'bg-accent-warning/20 text-accent-warning',
      RATE_LIMITED: 'bg-amber-500/20 text-amber-500',
    }
    const statusLabels: Record<string, string> = {
      ACTIVE: 'ACTIVE',
      PAUSED: 'PAUSED',
      ERROR: 'ERROR',
      PENDING: 'PENDING',
      RATE_LIMITED: 'RATE LIMITED',
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${statusStyles[source.status] || 'bg-text-muted/20 text-text-muted'}`}>
        {statusLabels[source.status] || source.status}
      </span>
    )
  }

  const getLastSyncText = () => {
    if (isSyncing) return 'Syncing now...'
    if (!source.last_sync_at) return 'Never synced'
    return formatRelativeTime(source.last_sync_at)
  }

  const getLocationText = () => {
    // If we have multiple folders, show folder count
    if (hasFolders && source.folders.length > 1) {
      return `${source.folders.length} folders`
    }
    // Single folder - show path/URL
    if (source.source_type === 'GOOGLE_DRIVE' && source.google_drive_url) {
      return source.google_drive_url
    }
    if (source.source_type === 'BULK_FOLDER' && source.folder_path) {
      return source.folder_path
    }
    // Check first folder
    if (hasFolders) {
      const folder = source.folders[0]
      return folder.google_drive_url || folder.folder_path || '-'
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
            {/* Expand button (show for any source that can have multiple folders) */}
            {canHaveMultipleFolders && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 text-text-muted hover:text-text-primary transition-colors flex-shrink-0 mt-2"
                aria-label={isExpanded ? 'Collapse folders' : 'Expand folders'}
              >
                <ChevronIcon className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
              </button>
            )}
            <div className="w-10 h-10 rounded-lg bg-bg-tertiary flex items-center justify-center text-text-secondary flex-shrink-0">
              {getSourceIcon()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-medium text-text-primary truncate">{source.name}</h3>
                <span className="text-xs text-text-muted bg-bg-tertiary px-2 py-0.5 rounded">
                  {getSourceTypeLabel()}
                </span>
                {source.default_designer && (
                  <span className="text-xs text-text-secondary">
                    Designer: {source.default_designer}
                  </span>
                )}
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
              title={source.source_type === 'UPLOAD' ? 'Upload sources cannot be synced' : 'Sync all folders'}
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

        {/* Error message if last sync failed or rate limited */}
        {(source.status === 'ERROR' || source.status === 'RATE_LIMITED') && source.last_sync_error && (
          <div className={`mt-3 px-3 py-2 rounded text-sm ${
            source.status === 'RATE_LIMITED'
              ? 'bg-amber-500/10 border border-amber-500/20 text-amber-500'
              : 'bg-accent-danger/10 border border-accent-danger/20 text-accent-danger'
          }`}>
            {source.last_sync_error}
          </div>
        )}
      </div>

      {/* Expanded folder list */}
      {isExpanded && canHaveMultipleFolders && (
        <div className="border-t border-bg-tertiary">
          <div className="px-4 py-2 bg-bg-tertiary/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                Folders ({source.folders.length})
              </span>
              {onAddFolder && source.source_type !== 'UPLOAD' && (
                <button
                  onClick={() => onAddFolder(source.id)}
                  className="text-xs text-accent-primary hover:text-accent-primary/80 flex items-center gap-1"
                >
                  <PlusIcon className="w-3 h-3" />
                  Add Folder
                </button>
              )}
            </div>
          </div>
          <div className="divide-y divide-bg-tertiary/50">
            {source.folders.length === 0 ? (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-text-muted">
                  No folders configured yet. Click "Add Folder" to add one.
                </p>
              </div>
            ) : (
              source.folders.map((folder) => (
                <FolderRow
                  key={folder.id}
                  folder={folder}
                  sourceType={source.source_type}
                  onSync={() => handleFolderSync(folder.id)}
                  onToggleEnabled={() => handleToggleFolderEnabled(folder)}
                  isSyncing={syncFolder.isPending}
                />
              ))
            )}
          </div>
        </div>
      )}

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
// Sub-components
// =============================================================================

interface FolderRowProps {
  folder: ImportSourceFolderSummary
  sourceType: string
  onSync: () => void
  onToggleEnabled: () => void
  isSyncing: boolean
}

function FolderRow({ folder, sourceType, onSync, onToggleEnabled, isSyncing }: FolderRowProps) {
  const displayName = folder.name || getFolderDisplayName(folder)
  const locationText = folder.google_drive_url || folder.folder_path || '-'

  return (
    <div className={`px-4 py-3 flex items-center gap-4 ${!folder.enabled ? 'opacity-50' : ''}`}>
      {/* Enable/disable toggle */}
      <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
        <input
          type="checkbox"
          checked={folder.enabled}
          onChange={onToggleEnabled}
          className="sr-only peer"
        />
        <div className="w-8 h-4 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-accent-primary"></div>
      </label>

      {/* Folder info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-text-primary truncate">{displayName}</span>
          {folder.has_overrides && (
            <span className="text-[10px] px-1.5 py-0.5 bg-accent-warning/20 text-accent-warning rounded">
              custom
            </span>
          )}
        </div>
        <p className="text-xs text-text-muted truncate" title={locationText}>
          {locationText}
        </p>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-text-muted flex-shrink-0">
        <span>{folder.items_imported} imported</span>
        {folder.last_synced_at && (
          <span>Synced {formatRelativeTime(folder.last_synced_at)}</span>
        )}
      </div>

      {/* Sync button */}
      {sourceType !== 'UPLOAD' && (
        <button
          onClick={onSync}
          disabled={isSyncing || !folder.enabled}
          className="p-1.5 text-text-muted hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Sync this folder"
        >
          {isSyncing ? (
            <SpinnerIcon className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshIcon className="w-4 h-4" />
          )}
        </button>
      )}
    </div>
  )
}

// =============================================================================
// Utilities
// =============================================================================

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function getFolderDisplayName(folder: ImportSourceFolderSummary): string {
  // Try to extract name from URL or path
  if (folder.google_drive_url) {
    // Try to get folder ID from URL as fallback name
    const match = folder.google_drive_url.match(/folders\/([a-zA-Z0-9_-]+)/)
    if (match) return `Folder ${match[1].substring(0, 8)}...`
  }
  if (folder.folder_path) {
    // Get last part of path
    const parts = folder.folder_path.split(/[/\\]/)
    return parts[parts.length - 1] || folder.folder_path
  }
  return 'Unnamed folder'
}

// =============================================================================
// Icons
// =============================================================================

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  )
}

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
