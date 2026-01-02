/**
 * Delete confirmation modal for import sources
 */
import { useState } from 'react'

interface DeleteSourceModalProps {
  isOpen: boolean
  sourceName: string
  onConfirm: (keepDesigns: boolean) => void
  onCancel: () => void
  isDeleting: boolean
}

export function DeleteSourceModal({
  isOpen,
  sourceName,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteSourceModalProps) {
  const [keepDesigns, setKeepDesigns] = useState(true)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="p-4 border-b border-bg-tertiary">
          <h2 className="text-lg font-semibold text-text-primary">Delete Import Source</h2>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <p className="text-text-secondary">
            Are you sure you want to delete <span className="font-medium text-text-primary">{sourceName}</span>?
          </p>

          {/* Keep designs option */}
          <div className="bg-bg-tertiary rounded-lg p-4 space-y-3">
            <p className="text-sm text-text-secondary">What should happen to the imported designs?</p>

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="keepDesigns"
                checked={keepDesigns}
                onChange={() => setKeepDesigns(true)}
                className="mt-1"
              />
              <div>
                <span className="text-text-primary font-medium">Keep designs</span>
                <p className="text-xs text-text-muted">Designs will remain in your catalog</p>
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="keepDesigns"
                checked={!keepDesigns}
                onChange={() => setKeepDesigns(false)}
                className="mt-1"
              />
              <div>
                <span className="text-text-primary font-medium">Delete designs</span>
                <p className="text-xs text-text-muted text-accent-danger">
                  All designs imported from this source will be deleted
                </p>
              </div>
            </label>
          </div>

          {!keepDesigns && (
            <div className="flex items-start gap-2 text-accent-warning text-sm bg-accent-warning/10 border border-accent-warning/20 rounded-lg p-3">
              <WarningIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>This action cannot be undone. The designs and their files will be permanently deleted.</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-bg-tertiary">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(keepDesigns)}
            disabled={isDeleting}
            className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger/80 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isDeleting && <SpinnerIcon className="w-4 h-4 animate-spin" />}
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
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
