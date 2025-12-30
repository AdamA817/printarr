import { useState } from 'react'

interface AddChannelModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: { title: string; username?: string }) => void
  isSubmitting: boolean
  error?: string | null
}

export function AddChannelModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: AddChannelModalProps) {
  const [title, setTitle] = useState('')
  const [username, setUsername] = useState('')

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return

    onSubmit({
      title: title.trim(),
      username: username.trim() || undefined,
    })
  }

  const handleClose = () => {
    setTitle('')
    setUsername('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <h2 className="text-lg font-semibold text-text-primary">
            Add Channel
          </h2>
          <button
            onClick={handleClose}
            className="text-text-secondary hover:text-text-primary"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 rounded bg-accent-danger/20 text-accent-danger text-sm">
              {error}
            </div>
          )}

          <div>
            <label
              htmlFor="title"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Channel Name *
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., 3D Printing Designs"
              className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
              required
            />
          </div>

          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Username (optional)
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g., @channel_username"
              className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
            />
            <p className="mt-1 text-xs text-text-muted">
              Telegram channel username (without @). Will be validated in future versions.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Adding...' : 'Add Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
