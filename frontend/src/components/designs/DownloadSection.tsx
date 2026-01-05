import { useState } from 'react'
import type { DesignStatus, DesignFile, FileKind } from '@/types/design'
import { useWantDesign, useDownloadDesign, useCancelDownload, useUpdateDesign, useDesignFiles } from '@/hooks/useDesigns'
import { designsApi } from '@/services/api'

// Format file size for display
function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return '--'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

// File kind icons and colors
const FILE_KIND_STYLES: Record<FileKind, { icon: string; color: string }> = {
  MODEL: { icon: '3D', color: 'text-accent-primary bg-accent-primary/10' },
  IMAGE: { icon: 'IMG', color: 'text-accent-success bg-accent-success/10' },
  CONFIG: { icon: 'CFG', color: 'text-accent-warning bg-accent-warning/10' },
  DOCUMENTATION: { icon: 'DOC', color: 'text-text-secondary bg-bg-tertiary' },
  OTHER: { icon: 'FILE', color: 'text-text-muted bg-bg-tertiary' },
}

interface DownloadSectionProps {
  designId: string
  status: DesignStatus
  onError?: (message: string) => void
}

// Priority levels for download queue (values match backend: Low=0, Normal=5, High=10, Urgent=20)
type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT'

const PRIORITY_LABELS: Record<Priority, string> = {
  LOW: 'Low',
  NORMAL: 'Normal',
  HIGH: 'High',
  URGENT: 'Urgent',
}

// Icon components
function HeartIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
    </svg>
  )
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`animate-spin ${className}`}
    >
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" strokeOpacity="1" />
    </svg>
  )
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  )
}

function SaveFileIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

export function DownloadSection({ designId, status, onError }: DownloadSectionProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const wantDesign = useWantDesign()
  const downloadDesign = useDownloadDesign()
  const cancelDownload = useCancelDownload()
  const updateDesign = useUpdateDesign()

  const handleAction = async (action: () => Promise<unknown>, errorMessage: string) => {
    if (isLoading) return
    setIsLoading(true)
    try {
      await action()
    } catch (error) {
      console.error(errorMessage, error)
      onError?.(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleWant = () => {
    handleAction(
      () => wantDesign.mutateAsync(designId),
      'Failed to mark as wanted'
    )
  }

  const handleDownload = () => {
    handleAction(
      () => downloadDesign.mutateAsync(designId),
      'Failed to start download'
    )
  }

  const handleCancel = () => {
    handleAction(
      () => cancelDownload.mutateAsync(designId),
      'Failed to cancel download'
    )
  }

  const handleRemoveFromQueue = () => {
    handleAction(
      () => cancelDownload.mutateAsync(designId),
      'Failed to remove from queue'
    )
  }

  const handleDeleteFiles = () => {
    handleAction(
      async () => {
        // This will call DELETE /api/v1/designs/{id}/files when backend is ready
        // For now, we reset to DISCOVERED status
        await updateDesign.mutateAsync({ id: designId, data: { status: 'DISCOVERED' } })
        setShowDeleteConfirm(false)
      },
      'Failed to delete files'
    )
  }

  const handleRedownload = () => {
    handleAction(
      () => downloadDesign.mutateAsync(designId),
      'Failed to start re-download'
    )
  }

  const renderContent = () => {
    switch (status) {
      case 'DISCOVERED':
        return (
          <div className="space-y-3">
            <p className="text-sm text-text-muted">
              This design hasn't been downloaded yet.
            </p>
            <button
              onClick={handleWant}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-accent-primary hover:bg-accent-primary/80 text-white font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? (
                <LoadingSpinner className="w-5 h-5" />
              ) : (
                <HeartIcon className="w-5 h-5" />
              )}
              Mark as Wanted
            </button>
          </div>
        )

      case 'WANTED':
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 rounded bg-accent-warning/20 text-accent-warning text-xs font-medium">
                In Queue
              </span>
            </div>

            <div className="space-y-3">
              <button
                onClick={handleDownload}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-accent-primary hover:bg-accent-primary/80 text-white font-medium transition-colors disabled:opacity-50"
              >
                {isLoading ? (
                  <LoadingSpinner className="w-5 h-5" />
                ) : (
                  <DownloadIcon className="w-5 h-5" />
                )}
                Download Now
              </button>

              <button
                onClick={handleRemoveFromQueue}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-bg-tertiary hover:bg-bg-tertiary/80 text-text-secondary hover:text-text-primary text-sm transition-colors disabled:opacity-50"
              >
                <XIcon className="w-4 h-4" />
                Remove from Queue
              </button>
            </div>

            {/* Priority Selector - for future implementation */}
            <div className="pt-3 border-t border-bg-tertiary">
              <label className="block text-xs text-text-muted mb-2">Priority</label>
              <select
                className="w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
                defaultValue="NORMAL"
                disabled
                title="Priority adjustment coming soon"
              >
                {(Object.keys(PRIORITY_LABELS) as Priority[]).map((priority) => (
                  <option key={priority} value={priority}>
                    {PRIORITY_LABELS[priority]}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-text-muted mt-1">
                Priority adjustment coming soon
              </p>
            </div>
          </div>
        )

      case 'DOWNLOADING':
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <LoadingSpinner className="w-4 h-4 text-accent-primary" />
              <span className="text-sm text-text-primary font-medium">Downloading...</span>
            </div>

            {/* Progress bar placeholder */}
            <div className="space-y-2">
              <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-primary rounded-full animate-pulse"
                  style={{ width: '45%' }}
                />
              </div>
              <div className="flex justify-between text-xs text-text-muted">
                <span>Downloading files...</span>
                <span>--</span>
              </div>
            </div>

            <button
              onClick={handleCancel}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-accent-danger/20 hover:bg-accent-danger/30 text-accent-danger text-sm font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? (
                <LoadingSpinner className="w-4 h-4" />
              ) : (
                <XIcon className="w-4 h-4" />
              )}
              Cancel Download
            </button>
          </div>
        )

      case 'DOWNLOADED':
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckIcon className="w-5 h-5 text-accent-success" />
              <span className="text-sm text-accent-success font-medium">Downloaded</span>
            </div>

            <p className="text-sm text-text-muted">
              Files are ready in the staging directory.
            </p>

            {/* File info placeholder */}
            <div className="bg-bg-tertiary rounded p-3 space-y-1">
              <p className="text-xs text-text-muted">Download location:</p>
              <p className="text-sm text-text-primary font-mono truncate">
                /staging/{designId.slice(0, 8)}/
              </p>
            </div>

            <div className="space-y-2 pt-3 border-t border-bg-tertiary">
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-accent-danger/20 hover:bg-accent-danger/30 text-accent-danger text-sm transition-colors disabled:opacity-50"
              >
                <TrashIcon className="w-4 h-4" />
                Delete Downloaded Files
              </button>
            </div>

            {/* Delete confirmation */}
            {showDeleteConfirm && (
              <div className="mt-3 p-3 bg-bg-tertiary rounded-lg">
                <p className="text-sm text-text-primary mb-3">
                  Delete downloaded files and reset to Discovered?
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteFiles}
                    disabled={isLoading}
                    className="text-xs px-3 py-1.5 rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
                  >
                    {isLoading ? 'Deleting...' : 'Yes, Delete'}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="text-xs px-3 py-1.5 rounded bg-bg-secondary text-text-secondary hover:text-text-primary transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )

      case 'ORGANIZED':
        return <OrganizedSection designId={designId} isLoading={isLoading} onRedownload={handleRedownload} />

      default:
        return null
    }
  }

  return (
    <section className="bg-bg-secondary rounded-lg p-4">
      <h3 className="text-sm font-medium text-text-muted mb-4">Download</h3>
      {renderContent()}
    </section>
  )
}

// Separate component for ORGANIZED status to use the files hook
function OrganizedSection({
  designId,
  isLoading,
  onRedownload,
}: {
  designId: string
  isLoading: boolean
  onRedownload: () => void
}) {
  const [showAllFiles, setShowAllFiles] = useState(false)
  const { data: files, isLoading: filesLoading } = useDesignFiles(designId, true)

  // Group files by kind
  const modelFiles = files?.filter((f) => f.file_kind === 'MODEL') || []
  const otherFiles = files?.filter((f) => f.file_kind !== 'MODEL') || []
  const totalSize = files?.reduce((acc, f) => acc + (f.size_bytes || 0), 0) || 0

  // Show max 5 files by default
  const displayFiles = showAllFiles ? files : files?.slice(0, 5)
  const hasMoreFiles = (files?.length || 0) > 5

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FolderIcon className="w-5 h-5 text-accent-success" />
        <span className="text-sm text-accent-success font-medium">In Library</span>
      </div>

      {/* File stats */}
      {files && files.length > 0 && (
        <div className="flex gap-3 text-xs text-text-muted">
          <span>{files.length} file{files.length !== 1 ? 's' : ''}</span>
          <span>{formatFileSize(totalSize)}</span>
          {modelFiles.length > 0 && (
            <span className="text-accent-primary">{modelFiles.length} model{modelFiles.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      )}

      {/* Download All as ZIP button */}
      <a
        href={designsApi.getDownloadAllUrl(designId)}
        download
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-accent-primary hover:bg-accent-primary/80 text-white font-medium transition-colors"
      >
        <SaveFileIcon className="w-5 h-5" />
        Download All (ZIP)
      </a>

      {/* Individual files section */}
      {filesLoading ? (
        <div className="pt-3 border-t border-bg-tertiary">
          <div className="animate-pulse space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-bg-tertiary rounded" />
            ))}
          </div>
        </div>
      ) : files && files.length > 0 ? (
        <div className="pt-3 border-t border-bg-tertiary">
          <p className="text-xs text-text-muted mb-2">Or download individual files:</p>
          <div className="space-y-1 max-h-[300px] overflow-y-auto">
            {displayFiles?.map((file) => (
              <FileDownloadRow key={file.id} file={file} designId={designId} />
            ))}
          </div>
          {hasMoreFiles && !showAllFiles && (
            <button
              onClick={() => setShowAllFiles(true)}
              className="mt-2 w-full text-xs text-accent-primary hover:text-accent-primary/80 py-1"
            >
              Show {(files?.length || 0) - 5} more files...
            </button>
          )}
          {showAllFiles && hasMoreFiles && (
            <button
              onClick={() => setShowAllFiles(false)}
              className="mt-2 w-full text-xs text-text-muted hover:text-text-primary py-1"
            >
              Show fewer
            </button>
          )}
        </div>
      ) : null}

      <div className="space-y-2 pt-3 border-t border-bg-tertiary">
        <button
          onClick={onRedownload}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-bg-tertiary hover:bg-bg-tertiary/80 text-text-secondary hover:text-text-primary text-sm transition-colors disabled:opacity-50"
        >
          {isLoading ? (
            <LoadingSpinner className="w-4 h-4" />
          ) : (
            <RefreshIcon className="w-4 h-4" />
          )}
          Re-download from Telegram
        </button>
      </div>
    </div>
  )
}

// Individual file download row
function FileDownloadRow({ file, designId }: { file: DesignFile; designId: string }) {
  const kindStyle = FILE_KIND_STYLES[file.file_kind] || FILE_KIND_STYLES.OTHER

  return (
    <a
      href={designsApi.getFileDownloadUrl(designId, file.id)}
      download={file.filename}
      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-bg-tertiary transition-colors group"
    >
      {/* File kind badge */}
      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${kindStyle.color}`}>
        {kindStyle.icon}
      </span>

      {/* Filename */}
      <span className="flex-1 text-sm text-text-primary truncate group-hover:text-accent-primary transition-colors">
        {file.filename}
      </span>

      {/* Primary indicator */}
      {file.is_primary && (
        <span className="text-[10px] text-accent-primary bg-accent-primary/10 px-1.5 py-0.5 rounded">
          PRIMARY
        </span>
      )}

      {/* File size */}
      <span className="text-xs text-text-muted">
        {formatFileSize(file.size_bytes)}
      </span>

      {/* Download icon */}
      <DownloadIcon className="w-4 h-4 text-text-muted group-hover:text-accent-primary opacity-0 group-hover:opacity-100 transition-all" />
    </a>
  )
}
