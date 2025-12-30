interface DeleteConfirmModalProps {
  isOpen: boolean
  channelTitle: string
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}

export function DeleteConfirmModal({
  isOpen,
  channelTitle,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-sm mx-4">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-2">
            Delete Channel
          </h2>
          <p className="text-text-secondary">
            Are you sure you want to delete{' '}
            <span className="font-medium text-text-primary">{channelTitle}</span>?
            This action cannot be undone.
          </p>

          <div className="flex justify-end gap-3 mt-6">
            <button
              onClick={onCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isDeleting}
              className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
