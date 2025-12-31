import { useState } from 'react'
import type { DiscoveredChannel } from '@/types/discovered-channel'
import type { BackfillMode, DownloadMode } from '@/types/channel'
import { useAddDiscoveredChannel } from '@/hooks/useDiscoveredChannels'

interface AddDiscoveredChannelModalProps {
  isOpen: boolean
  channel: DiscoveredChannel | null
  onClose: () => void
  onSuccess: (channelId: string, title: string) => void
}

export function AddDiscoveredChannelModal({
  isOpen,
  channel,
  onClose,
  onSuccess,
}: AddDiscoveredChannelModalProps) {
  const [downloadMode, setDownloadMode] = useState<DownloadMode>('MANUAL')
  const [backfillMode, setBackfillMode] = useState<BackfillMode>('LAST_N_MESSAGES')
  const [backfillValue, setBackfillValue] = useState(100)
  const [isEnabled, setIsEnabled] = useState(true)

  const addChannel = useAddDiscoveredChannel()

  if (!isOpen || !channel) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    try {
      const result = await addChannel.mutateAsync({
        id: channel.id,
        request: {
          download_mode: downloadMode,
          backfill_mode: backfillMode,
          backfill_value: backfillValue,
          is_enabled: isEnabled,
          remove_from_discovered: true,
        },
      })
      onSuccess(result.channel_id, result.title)
      onClose()
    } catch (error) {
      console.error('Failed to add channel:', error)
    }
  }

  const displayTitle = channel.title || channel.username || 'Unknown Channel'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <h2 className="text-lg font-semibold text-text-primary">
            Add Channel
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
          {/* Channel Info */}
          <div className="p-3 rounded-lg bg-bg-tertiary">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-bg-primary flex items-center justify-center text-text-secondary">
                {channel.is_private ? '🔒' : '📡'}
              </div>
              <div>
                <h3 className="font-medium text-text-primary">{displayTitle}</h3>
                {channel.username && (
                  <p className="text-sm text-text-secondary">@{channel.username}</p>
                )}
              </div>
            </div>
            <div className="mt-2 text-sm text-text-secondary">
              Referenced {channel.reference_count} time{channel.reference_count !== 1 ? 's' : ''}
            </div>
          </div>

          {addChannel.error && (
            <div className="p-3 rounded-lg bg-accent-danger/20 border border-accent-danger/30">
              <p className="text-sm text-accent-danger">
                {(addChannel.error as Error).message || 'Failed to add channel'}
              </p>
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
              <option value="DOWNLOAD_ALL_NEW">Auto-Download New</option>
              <option value="DOWNLOAD_ALL">Auto-Download All</option>
            </select>
          </div>

          {/* Backfill Mode */}
          <div>
            <label
              htmlFor="backfill-mode"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Initial Backfill
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

          {/* Backfill Value */}
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
                onChange={(e) => setBackfillValue(parseInt(e.target.value) || 100)}
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
              />
            </div>
          )}

          {/* Enabled Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-text-secondary">
                Enable Channel
              </label>
              <p className="text-xs text-text-muted">
                Start monitoring immediately
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
              disabled={addChannel.isPending}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {addChannel.isPending && <Spinner className="w-4 h-4" />}
              {addChannel.isPending ? 'Adding...' : 'Add Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
