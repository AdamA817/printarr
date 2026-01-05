import { useState, useEffect } from 'react'
import { useSettings, useUpdateSetting } from '@/hooks/useSettings'
import {
  DEFAULT_SYNC_ENABLED,
  DEFAULT_SYNC_POLL_INTERVAL,
  DEFAULT_SYNC_BATCH_SIZE,
} from '@/types/settings'

export function SyncSettings() {
  const { data: settings, isLoading } = useSettings()
  const updateSetting = useUpdateSetting()

  // Local state for form
  const [syncEnabled, setSyncEnabled] = useState(DEFAULT_SYNC_ENABLED)
  const [pollInterval, setPollInterval] = useState(DEFAULT_SYNC_POLL_INTERVAL)
  const [batchSize, setBatchSize] = useState(DEFAULT_SYNC_BATCH_SIZE)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    if (settings) {
      setSyncEnabled((settings.sync_enabled as boolean) ?? DEFAULT_SYNC_ENABLED)
      setPollInterval((settings.sync_poll_interval as number) ?? DEFAULT_SYNC_POLL_INTERVAL)
      setBatchSize((settings.sync_batch_size as number) ?? DEFAULT_SYNC_BATCH_SIZE)
    }
  }, [settings])

  // Track changes
  useEffect(() => {
    if (!settings) return
    setHasChanges(
      syncEnabled !== ((settings.sync_enabled as boolean) ?? DEFAULT_SYNC_ENABLED) ||
      pollInterval !== ((settings.sync_poll_interval as number) ?? DEFAULT_SYNC_POLL_INTERVAL) ||
      batchSize !== ((settings.sync_batch_size as number) ?? DEFAULT_SYNC_BATCH_SIZE)
    )
  }, [syncEnabled, pollInterval, batchSize, settings])

  // Validation
  const pollIntervalError = pollInterval < 60 || pollInterval > 3600 ? 'Must be between 60 and 3600' : null
  const batchSizeError = batchSize < 10 || batchSize > 500 ? 'Must be between 10 and 500' : null

  const handleSave = async () => {
    if (pollIntervalError || batchSizeError) return

    setSaveStatus('saving')
    try {
      await Promise.all([
        updateSetting.mutateAsync({ key: 'sync_enabled', value: syncEnabled }),
        updateSetting.mutateAsync({ key: 'sync_poll_interval', value: pollInterval }),
        updateSetting.mutateAsync({ key: 'sync_batch_size', value: batchSize }),
      ])
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save sync settings:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  // Format seconds to human-readable
  const formatInterval = (seconds: number): string => {
    if (seconds < 120) return `${seconds}s`
    return `${Math.floor(seconds / 60)}m`
  }

  if (isLoading) {
    return <SettingsSkeleton />
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4">
        Sync Settings
      </h3>

      <div className="space-y-6">
        {/* Sync Enabled Toggle */}
        <div>
          <div className="flex items-start justify-between">
            <div>
              <label
                htmlFor="sync-enabled"
                className="block text-sm font-medium text-text-primary mb-1"
              >
                Enable Live Monitoring
              </label>
              <p className="text-sm text-text-secondary">
                Automatically monitor channels for new messages and designs.
              </p>
              <p className="text-xs text-accent-warning mt-1 flex items-center gap-1">
                <RestartIcon className="w-3 h-3" />
                Requires restart to take effect
              </p>
            </div>
            <button
              id="sync-enabled"
              role="switch"
              aria-checked={syncEnabled}
              onClick={() => setSyncEnabled(!syncEnabled)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary ${
                syncEnabled ? 'bg-accent-primary' : 'bg-bg-tertiary'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  syncEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Poll Interval */}
        <div>
          <label
            htmlFor="poll-interval"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Poll Interval
          </label>
          <p className="text-sm text-text-secondary mb-3">
            How often to check for messages that may have been missed during downtime.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="poll-interval"
              type="range"
              min={60}
              max={3600}
              step={60}
              value={pollInterval}
              onChange={(e) => setPollInterval(Number(e.target.value))}
              className="flex-1 h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
            />
            <span className="w-16 text-right text-sm text-text-primary font-mono">{formatInterval(pollInterval)}</span>
          </div>
          {pollIntervalError && (
            <p className="mt-2 text-sm text-accent-danger">{pollIntervalError}</p>
          )}
        </div>

        {/* Batch Size */}
        <div>
          <label
            htmlFor="batch-size"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Batch Size
          </label>
          <p className="text-sm text-text-secondary mb-3">
            Maximum messages to process per sync cycle. Larger values may use more memory.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="batch-size"
              type="range"
              min={10}
              max={500}
              step={10}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="flex-1 h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
            />
            <span className="w-20 text-right text-sm text-text-primary font-mono">{batchSize} msgs</span>
          </div>
          {batchSizeError && (
            <p className="mt-2 text-sm text-accent-danger">{batchSizeError}</p>
          )}
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!pollIntervalError || !!batchSizeError || saveStatus === 'saving'}
              className="px-4 py-2 rounded bg-accent-primary text-white font-medium hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saveStatus === 'saving' ? 'Saving...' : 'Save Changes'}
            </button>
            {saveStatus === 'success' && (
              <span className="text-sm text-accent-success flex items-center gap-1">
                <CheckIcon className="w-4 h-4" />
                Saved
              </span>
            )}
            {saveStatus === 'error' && (
              <span className="text-sm text-accent-danger">
                Failed to save. Please try again.
              </span>
            )}
          </div>
        )}
      </div>
    </div>
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

function RestartIcon({ className }: { className?: string }) {
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
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </svg>
  )
}

function SettingsSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="h-6 bg-bg-tertiary rounded w-36 mb-4" />
      <div className="space-y-6">
        {[...Array(3)].map((_, i) => (
          <div key={i}>
            <div className="h-4 bg-bg-tertiary rounded w-40 mb-2" />
            <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-3" />
            <div className="h-8 bg-bg-tertiary rounded w-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
