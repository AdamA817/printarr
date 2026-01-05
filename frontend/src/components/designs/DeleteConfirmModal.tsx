import { useState } from 'react'

interface DeleteConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (deleteFiles: boolean) => Promise<void>
  designTitle: string
  isPending: boolean
  /** If true, show options for deleting files (for ORGANIZED designs) */
  hasFiles?: boolean
}

export function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  designTitle,
  isPending,
  hasFiles = false,
}: DeleteConfirmModalProps) {
  const [deleteFiles, setDeleteFiles] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleConfirm = async () => {
    setError(null)
    try {
      await onConfirm(deleteFiles)
    } catch (err) {
      setError((err as Error).message || 'Failed to delete design')
    }
  }

  const handleClose = () => {
    if (!isPending) {
      setDeleteFiles(false)
      setError(null)
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md bg-bg-primary rounded-lg shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-bg-tertiary">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-accent-danger/20 rounded-lg">
                <TrashIcon className="w-5 h-5 text-accent-danger" />
              </div>
              <h2 className="text-lg font-medium text-text-primary">
                Delete Design
              </h2>
            </div>
            <button
              onClick={handleClose}
              disabled={isPending}
              className="p-2 rounded text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors disabled:opacity-50"
              aria-label="Close"
            >
              <CloseIcon />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            <p className="text-text-secondary">
              Are you sure you want to delete{' '}
              <span className="font-medium text-text-primary">"{designTitle}"</span>?
            </p>

            {hasFiles && (
              <div className="space-y-3 pt-2">
                <p className="text-sm text-text-muted">
                  Choose what to delete:
                </p>
                <label className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary cursor-pointer hover:bg-bg-tertiary transition-colors">
                  <input
                    type="radio"
                    name="deleteOption"
                    checked={!deleteFiles}
                    onChange={() => setDeleteFiles(false)}
                    className="mt-0.5 text-accent-primary focus:ring-accent-primary"
                  />
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      Database only
                    </p>
                    <p className="text-xs text-text-muted mt-0.5">
                      Remove from Printarr but keep files in library
                    </p>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary cursor-pointer hover:bg-bg-tertiary transition-colors">
                  <input
                    type="radio"
                    name="deleteOption"
                    checked={deleteFiles}
                    onChange={() => setDeleteFiles(true)}
                    className="mt-0.5 text-accent-danger focus:ring-accent-danger"
                  />
                  <div>
                    <p className="text-sm font-medium text-accent-danger">
                      Database + Files
                    </p>
                    <p className="text-xs text-text-muted mt-0.5">
                      Remove from Printarr and delete all files from disk
                    </p>
                  </div>
                </label>
              </div>
            )}

            {!hasFiles && (
              <p className="text-sm text-text-muted">
                This will remove the design from your catalog. This action cannot be undone.
              </p>
            )}

            {error && (
              <div className="p-3 bg-accent-danger/20 rounded-lg">
                <p className="text-sm text-accent-danger">{error}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-bg-tertiary">
            <button
              onClick={handleClose}
              disabled={isPending}
              className="px-4 py-2 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isPending}
              className="px-4 py-2 text-sm rounded bg-accent-danger text-white hover:bg-accent-danger/80 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {isPending && <LoadingSpinner className="w-4 h-4" />}
              {isPending ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Icon components
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

function CloseIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
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
