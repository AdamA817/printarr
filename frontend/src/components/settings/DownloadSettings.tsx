import { useState, useEffect } from 'react'
import { useLibrarySettings, useUpdateSetting } from '@/hooks/useSettings'
import { DEFAULT_MAX_CONCURRENT_DOWNLOADS, DEFAULT_DELETE_ARCHIVES } from '@/types/settings'

export function DownloadSettings() {
  const { settings, isLoading } = useLibrarySettings()
  const updateSetting = useUpdateSetting()

  // Local state for form
  const [maxConcurrent, setMaxConcurrent] = useState(DEFAULT_MAX_CONCURRENT_DOWNLOADS)
  const [deleteArchives, setDeleteArchives] = useState(DEFAULT_DELETE_ARCHIVES)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    setMaxConcurrent(settings.max_concurrent_downloads)
    setDeleteArchives(settings.delete_archives_after_extraction)
  }, [settings.max_concurrent_downloads, settings.delete_archives_after_extraction])

  // Track changes
  useEffect(() => {
    setHasChanges(
      maxConcurrent !== settings.max_concurrent_downloads ||
      deleteArchives !== settings.delete_archives_after_extraction
    )
  }, [maxConcurrent, deleteArchives, settings])

  // Validation
  const maxConcurrentError =
    maxConcurrent < 1 || maxConcurrent > 10
      ? 'Must be between 1 and 10'
      : null

  const handleSave = async () => {
    if (maxConcurrentError) return

    setSaveStatus('saving')
    try {
      // Save both settings
      await Promise.all([
        updateSetting.mutateAsync({
          key: 'max_concurrent_downloads',
          value: maxConcurrent,
        }),
        updateSetting.mutateAsync({
          key: 'delete_archives_after_extraction',
          value: deleteArchives,
        }),
      ])
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save download settings:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return <DownloadSettingsSkeleton />
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4">
        Download Settings
      </h3>

      <div className="space-y-6">
        {/* Max Concurrent Downloads */}
        <div>
          <label
            htmlFor="max-concurrent"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Maximum Concurrent Downloads
          </label>
          <p className="text-sm text-text-secondary mb-3">
            How many files can be downloaded simultaneously. Higher values may speed up downloads but use more resources.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="max-concurrent"
              type="number"
              min={1}
              max={10}
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(Number(e.target.value))}
              className={`w-24 px-3 py-2 rounded bg-bg-tertiary text-text-primary border ${
                maxConcurrentError
                  ? 'border-accent-danger focus:ring-accent-danger'
                  : 'border-transparent focus:ring-accent-primary'
              } focus:outline-none focus:ring-2`}
            />
            <span className="text-sm text-text-muted">downloads</span>
          </div>
          {maxConcurrentError && (
            <p className="mt-2 text-sm text-accent-danger">{maxConcurrentError}</p>
          )}
        </div>

        {/* Delete Archives Toggle */}
        <div>
          <div className="flex items-start justify-between">
            <div>
              <label
                htmlFor="delete-archives"
                className="block text-sm font-medium text-text-primary mb-1"
              >
                Delete Archives After Extraction
              </label>
              <p className="text-sm text-text-secondary">
                Automatically remove ZIP/RAR files after extracting their contents to save disk space.
              </p>
            </div>
            <button
              id="delete-archives"
              role="switch"
              aria-checked={deleteArchives}
              onClick={() => setDeleteArchives(!deleteArchives)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary ${
                deleteArchives ? 'bg-accent-primary' : 'bg-bg-tertiary'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  deleteArchives ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!maxConcurrentError || saveStatus === 'saving'}
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

function DownloadSettingsSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="h-6 bg-bg-tertiary rounded w-40 mb-4" />
      <div className="space-y-6">
        <div>
          <div className="h-4 bg-bg-tertiary rounded w-48 mb-2" />
          <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-3" />
          <div className="h-10 bg-bg-tertiary rounded w-24" />
        </div>
        <div className="flex justify-between">
          <div className="space-y-2">
            <div className="h-4 bg-bg-tertiary rounded w-48" />
            <div className="h-4 bg-bg-tertiary rounded w-64" />
          </div>
          <div className="h-6 bg-bg-tertiary rounded w-11" />
        </div>
      </div>
    </div>
  )
}
