import { useState } from 'react'
import type { DesignStatus } from '@/types/design'
import { useWantDesign, useDownloadDesign, useCancelDownload, useUpdateDesign } from '@/hooks/useDesigns'

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
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <FolderIcon className="w-5 h-5 text-accent-success" />
              <span className="text-sm text-accent-success font-medium">In Library</span>
            </div>

            <p className="text-sm text-text-muted">
              This design has been organized into your library.
            </p>

            {/* Library location placeholder */}
            <div className="bg-bg-tertiary rounded p-3 space-y-1">
              <p className="text-xs text-text-muted">Library location:</p>
              <p className="text-sm text-text-primary font-mono truncate">
                /library/designs/
              </p>
            </div>

            <div className="space-y-2 pt-3 border-t border-bg-tertiary">
              <button
                onClick={handleRedownload}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-bg-tertiary hover:bg-bg-tertiary/80 text-text-secondary hover:text-text-primary text-sm transition-colors disabled:opacity-50"
              >
                {isLoading ? (
                  <LoadingSpinner className="w-4 h-4" />
                ) : (
                  <RefreshIcon className="w-4 h-4" />
                )}
                Re-download
              </button>
            </div>
          </div>
        )

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
