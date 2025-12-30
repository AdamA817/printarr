import { useState, useEffect } from 'react'
import type { Channel, ChannelUpdate, BackfillMode, DownloadMode } from '@/types/channel'

interface EditChannelModalProps {
  isOpen: boolean
  channel: Channel | null
  onClose: () => void
  onSubmit: (id: string, data: ChannelUpdate) => void
  isSubmitting: boolean
  error?: string | null
}

export function EditChannelModal({
  isOpen,
  channel,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: EditChannelModalProps) {
  const [title, setTitle] = useState('')
  const [isEnabled, setIsEnabled] = useState(true)
  const [backfillMode, setBackfillMode] = useState<BackfillMode>('ALL_HISTORY')
  const [backfillValue, setBackfillValue] = useState(0)
  const [downloadMode, setDownloadMode] = useState<DownloadMode>('MANUAL')

  // Pre-fill form when channel changes
  useEffect(() => {
    if (channel) {
      setTitle(channel.title)
      setIsEnabled(channel.is_enabled)
      setBackfillMode(channel.backfill_mode)
      setBackfillValue(channel.backfill_value)
      setDownloadMode(channel.download_mode)
    }
  }, [channel])

  if (!isOpen || !channel) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return

    const updates: ChannelUpdate = {}

    // Only include changed fields
    if (title.trim() !== channel.title) {
      updates.title = title.trim()
    }
    if (isEnabled !== channel.is_enabled) {
      updates.is_enabled = isEnabled
    }
    if (backfillMode !== channel.backfill_mode) {
      updates.backfill_mode = backfillMode
    }
    if (backfillValue !== channel.backfill_value) {
      updates.backfill_value = backfillValue
    }
    if (downloadMode !== channel.download_mode) {
      updates.download_mode = downloadMode
    }

    // Only submit if there are actual changes
    if (Object.keys(updates).length === 0) {
      onClose()
      return
    }

    onSubmit(channel.id, updates)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <h2 className="text-lg font-semibold text-text-primary">
            Edit Channel
          </h2>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-accent-danger/20 border border-accent-danger/30">
              <p className="text-sm text-accent-danger">{error}</p>
            </div>
          )}

          {/* Title */}
          <div>
            <label
              htmlFor="edit-title"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Display Name *
            </label>
            <input
              id="edit-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Channel display name"
              className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
              required
            />
          </div>

          {/* Enabled Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-text-secondary">
                Channel Enabled
              </label>
              <p className="text-xs text-text-muted">
                Enable or disable message ingestion
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsEnabled(!isEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                isEnabled ? 'bg-accent-success' : 'bg-bg-tertiary'
              }`}
              role="switch"
              aria-checked={isEnabled}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Backfill Mode */}
          <div>
            <label
              htmlFor="backfill-mode"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Backfill Mode
            </label>
            <select
              id="backfill-mode"
              value={backfillMode}
              onChange={(e) => setBackfillMode(e.target.value as BackfillMode)}
              className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="ALL_HISTORY">All History</option>
              <option value="LAST_N_MESSAGES">Last N Messages</option>
              <option value="LAST_N_DAYS">Last N Days</option>
            </select>
          </div>

          {/* Backfill Value (only show when relevant) */}
          {backfillMode !== 'ALL_HISTORY' && (
            <div>
              <label
                htmlFor="backfill-value"
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                {backfillMode === 'LAST_N_MESSAGES' ? 'Number of Messages' : 'Number of Days'}
              </label>
              <input
                id="backfill-value"
                type="number"
                min="1"
                value={backfillValue}
                onChange={(e) => setBackfillValue(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
              />
            </div>
          )}

          {/* Download Mode */}
          <div>
            <label
              htmlFor="download-mode"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Download Mode
            </label>
            <select
              id="download-mode"
              value={downloadMode}
              onChange={(e) => setDownloadMode(e.target.value as DownloadMode)}
              className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="MANUAL">Manual</option>
              <option value="DOWNLOAD_ALL">Download All</option>
              <option value="DOWNLOAD_ALL_NEW">Download All New</option>
            </select>
            <p className="mt-1 text-xs text-text-muted">
              {downloadMode === 'MANUAL' && 'Manually approve each download'}
              {downloadMode === 'DOWNLOAD_ALL' && 'Automatically download all designs'}
              {downloadMode === 'DOWNLOAD_ALL_NEW' && 'Automatically download new designs only'}
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting && <Spinner className="w-4 h-4" />}
              {isSubmitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
