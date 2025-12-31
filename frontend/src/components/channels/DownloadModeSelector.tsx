import { useState, useEffect } from 'react'
import type { DownloadMode } from '@/types/channel'
import { useDownloadModePreview, useUpdateDownloadMode } from '@/hooks/useChannels'

interface DownloadModeSelectorProps {
  channelId: string
  currentMode: DownloadMode
  onModeChange?: (mode: DownloadMode) => void
}

const modeOptions: { value: DownloadMode; label: string; description: string }[] = [
  {
    value: 'MANUAL',
    label: 'Manual',
    description: 'You approve each download individually',
  },
  {
    value: 'DOWNLOAD_ALL_NEW',
    label: 'Auto-Download New',
    description: 'Automatically download new designs as they are discovered',
  },
  {
    value: 'DOWNLOAD_ALL',
    label: 'Auto-Download All',
    description: 'Download all existing designs and automatically download new ones',
  },
]

export function DownloadModeSelector({
  channelId,
  currentMode,
  onModeChange,
}: DownloadModeSelectorProps) {
  const [selectedMode, setSelectedMode] = useState<DownloadMode>(currentMode)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)

  const { data: preview, isLoading: isLoadingPreview } = useDownloadModePreview(
    channelId,
    showConfirmDialog ? 'DOWNLOAD_ALL' : null
  )

  const updateDownloadMode = useUpdateDownloadMode()

  // Reset selected mode when currentMode changes (e.g., from parent)
  useEffect(() => {
    setSelectedMode(currentMode)
  }, [currentMode])

  const handleModeSelect = (mode: DownloadMode) => {
    setSelectedMode(mode)

    if (mode === 'DOWNLOAD_ALL' && mode !== currentMode) {
      // Show confirmation dialog for DOWNLOAD_ALL
      setShowConfirmDialog(true)
    } else if (mode !== currentMode) {
      // Direct update for other modes
      applyModeChange(mode, false)
    }
  }

  const applyModeChange = async (mode: DownloadMode, confirmBulk: boolean) => {
    try {
      await updateDownloadMode.mutateAsync({
        channelId,
        request: {
          download_mode: mode,
          confirm_bulk_download: confirmBulk,
        },
      })
      onModeChange?.(mode)
      setShowConfirmDialog(false)
    } catch (error) {
      console.error('Failed to update download mode:', error)
      // Reset to current mode on error
      setSelectedMode(currentMode)
    }
  }

  const handleConfirmBulkDownload = () => {
    applyModeChange('DOWNLOAD_ALL', true)
  }

  const handleCancelConfirmation = () => {
    setShowConfirmDialog(false)
    setSelectedMode(currentMode)
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-text-secondary">
        Download Mode
      </label>

      <div className="space-y-2">
        {modeOptions.map((option) => (
          <label
            key={option.value}
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              selectedMode === option.value
                ? 'border-accent-primary bg-accent-primary/10'
                : 'border-bg-tertiary hover:border-text-muted'
            }`}
          >
            <input
              type="radio"
              name="downloadMode"
              value={option.value}
              checked={selectedMode === option.value}
              onChange={() => handleModeSelect(option.value)}
              disabled={updateDownloadMode.isPending}
              className="mt-1 text-accent-primary focus:ring-accent-primary"
            />
            <div className="flex-1">
              <div className="font-medium text-text-primary">{option.label}</div>
              <div className="text-sm text-text-secondary">{option.description}</div>
            </div>
          </label>
        ))}
      </div>

      {/* Update status */}
      {updateDownloadMode.isPending && (
        <p className="text-sm text-text-secondary">Updating download mode...</p>
      )}
      {updateDownloadMode.isError && (
        <p className="text-sm text-accent-danger">
          Failed to update: {(updateDownloadMode.error as Error).message}
        </p>
      )}

      {/* Confirmation Dialog for DOWNLOAD_ALL */}
      {showConfirmDialog && (
        <DownloadAllConfirmDialog
          designCount={preview?.designs_to_queue ?? 0}
          isLoading={isLoadingPreview}
          isPending={updateDownloadMode.isPending}
          onConfirm={handleConfirmBulkDownload}
          onCancel={handleCancelConfirmation}
        />
      )}
    </div>
  )
}

interface DownloadAllConfirmDialogProps {
  designCount: number
  isLoading: boolean
  isPending: boolean
  onConfirm: () => void
  onCancel: () => void
}

function DownloadAllConfirmDialog({
  designCount,
  isLoading,
  isPending,
  onConfirm,
  onCancel,
}: DownloadAllConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />

      {/* Dialog */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-2">
          Enable Auto-Download All?
        </h3>

        {isLoading ? (
          <div className="flex items-center gap-2 text-text-secondary py-4">
            <Spinner className="w-5 h-5" />
            <span>Calculating designs to download...</span>
          </div>
        ) : (
          <>
            <p className="text-text-secondary mb-4">
              This will queue <strong className="text-text-primary">{designCount}</strong> existing
              {designCount === 1 ? ' design' : ' designs'} for download and automatically
              download all future designs from this channel.
            </p>

            {designCount > 50 && (
              <div className="p-3 mb-4 rounded-lg bg-accent-warning/20 border border-accent-warning/30">
                <p className="text-sm text-accent-warning">
                  This is a large number of designs. Downloads will be queued and
                  processed in order.
                </p>
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onCancel}
                disabled={isPending}
                className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={isPending}
                className="px-4 py-2 bg-accent-success text-white rounded-lg hover:bg-accent-success/80 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isPending && <Spinner className="w-4 h-4" />}
                {isPending ? 'Enabling...' : `Download ${designCount} Designs`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
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
