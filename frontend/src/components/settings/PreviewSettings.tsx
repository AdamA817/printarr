import { useState, useEffect } from 'react'
import { useSettings, useUpdateSetting } from '@/hooks/useSettings'
import {
  DEFAULT_AUTO_QUEUE_RENDER,
  DEFAULT_RENDER_PRIORITY,
  DEFAULT_UPLOAD_MAX_SIZE,
  DEFAULT_UPLOAD_RETENTION,
} from '@/types/settings'

export function PreviewSettings() {
  const { data: settings, isLoading } = useSettings()
  const updateSetting = useUpdateSetting()

  // Local state for form
  const [autoQueueRender, setAutoQueueRender] = useState(DEFAULT_AUTO_QUEUE_RENDER)
  const [renderPriority, setRenderPriority] = useState(DEFAULT_RENDER_PRIORITY)
  const [maxUploadSize, setMaxUploadSize] = useState(DEFAULT_UPLOAD_MAX_SIZE)
  const [retentionHours, setRetentionHours] = useState(DEFAULT_UPLOAD_RETENTION)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    if (settings) {
      setAutoQueueRender((settings.auto_queue_render_after_import as boolean) ?? DEFAULT_AUTO_QUEUE_RENDER)
      setRenderPriority((settings.auto_queue_render_priority as number) ?? DEFAULT_RENDER_PRIORITY)
      setMaxUploadSize((settings.upload_max_size_mb as number) ?? DEFAULT_UPLOAD_MAX_SIZE)
      setRetentionHours((settings.upload_retention_hours as number) ?? DEFAULT_UPLOAD_RETENTION)
    }
  }, [settings])

  // Track changes
  useEffect(() => {
    if (!settings) return
    setHasChanges(
      autoQueueRender !== ((settings.auto_queue_render_after_import as boolean) ?? DEFAULT_AUTO_QUEUE_RENDER) ||
      renderPriority !== ((settings.auto_queue_render_priority as number) ?? DEFAULT_RENDER_PRIORITY) ||
      maxUploadSize !== ((settings.upload_max_size_mb as number) ?? DEFAULT_UPLOAD_MAX_SIZE) ||
      retentionHours !== ((settings.upload_retention_hours as number) ?? DEFAULT_UPLOAD_RETENTION)
    )
  }, [autoQueueRender, renderPriority, maxUploadSize, retentionHours, settings])

  // Validation
  const priorityError = renderPriority < -10 || renderPriority > 10 ? 'Must be between -10 and 10' : null
  const maxSizeError = maxUploadSize < 1 || maxUploadSize > 10000 ? 'Must be between 1 and 10000' : null
  const retentionError = retentionHours < 1 || retentionHours > 168 ? 'Must be between 1 and 168' : null

  const handleSave = async () => {
    if (priorityError || maxSizeError || retentionError) return

    setSaveStatus('saving')
    try {
      await Promise.all([
        updateSetting.mutateAsync({ key: 'auto_queue_render_after_import', value: autoQueueRender }),
        updateSetting.mutateAsync({ key: 'auto_queue_render_priority', value: renderPriority }),
        updateSetting.mutateAsync({ key: 'upload_max_size_mb', value: maxUploadSize }),
        updateSetting.mutateAsync({ key: 'upload_retention_hours', value: retentionHours }),
      ])
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save preview settings:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return <SettingsSkeleton />
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4">
        Preview & Upload Settings
      </h3>

      <div className="space-y-6">
        {/* Auto Queue Render Toggle */}
        <div>
          <div className="flex items-start justify-between">
            <div>
              <label
                htmlFor="auto-queue-render"
                className="block text-sm font-medium text-text-primary mb-1"
              >
                Auto-Queue Preview Renders
              </label>
              <p className="text-sm text-text-secondary">
                Automatically queue 3D preview renders after importing new designs.
              </p>
            </div>
            <button
              id="auto-queue-render"
              role="switch"
              aria-checked={autoQueueRender}
              onClick={() => setAutoQueueRender(!autoQueueRender)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary ${
                autoQueueRender ? 'bg-accent-primary' : 'bg-bg-tertiary'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  autoQueueRender ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Render Priority */}
        <div>
          <label
            htmlFor="render-priority"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Render Job Priority
          </label>
          <p className="text-sm text-text-secondary mb-3">
            Priority for auto-queued render jobs. Lower values run after higher priority jobs.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="render-priority"
              type="range"
              min={-10}
              max={10}
              step={1}
              value={renderPriority}
              onChange={(e) => setRenderPriority(Number(e.target.value))}
              className="flex-1 h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
            />
            <span className="w-12 text-right text-sm text-text-primary font-mono">{renderPriority}</span>
          </div>
          {priorityError && (
            <p className="mt-2 text-sm text-accent-danger">{priorityError}</p>
          )}
        </div>

        <div className="border-t border-bg-tertiary pt-6">
          <h4 className="text-sm font-medium text-text-secondary mb-4">Upload Limits</h4>

          {/* Max Upload Size */}
          <div className="mb-6">
            <label
              htmlFor="max-upload"
              className="block text-sm font-medium text-text-primary mb-2"
            >
              Maximum Upload Size
            </label>
            <p className="text-sm text-text-secondary mb-3">
              Maximum file size allowed for uploads (in megabytes).
            </p>
            <div className="flex items-center gap-4">
              <input
                id="max-upload"
                type="number"
                min={1}
                max={10000}
                value={maxUploadSize}
                onChange={(e) => setMaxUploadSize(Number(e.target.value))}
                className={`w-28 px-3 py-2 rounded bg-bg-tertiary text-text-primary border ${
                  maxSizeError
                    ? 'border-accent-danger focus:ring-accent-danger'
                    : 'border-transparent focus:ring-accent-primary'
                } focus:outline-none focus:ring-2`}
              />
              <span className="text-sm text-text-muted">MB</span>
            </div>
            {maxSizeError && (
              <p className="mt-2 text-sm text-accent-danger">{maxSizeError}</p>
            )}
          </div>

          {/* Retention Hours */}
          <div>
            <label
              htmlFor="retention-hours"
              className="block text-sm font-medium text-text-primary mb-2"
            >
              Upload Retention
            </label>
            <p className="text-sm text-text-secondary mb-3">
              Hours to keep unprocessed uploads before automatic cleanup.
            </p>
            <div className="flex items-center gap-4">
              <input
                id="retention-hours"
                type="number"
                min={1}
                max={168}
                value={retentionHours}
                onChange={(e) => setRetentionHours(Number(e.target.value))}
                className={`w-28 px-3 py-2 rounded bg-bg-tertiary text-text-primary border ${
                  retentionError
                    ? 'border-accent-danger focus:ring-accent-danger'
                    : 'border-transparent focus:ring-accent-primary'
                } focus:outline-none focus:ring-2`}
              />
              <span className="text-sm text-text-muted">hours</span>
            </div>
            {retentionError && (
              <p className="mt-2 text-sm text-accent-danger">{retentionError}</p>
            )}
          </div>
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!priorityError || !!maxSizeError || !!retentionError || saveStatus === 'saving'}
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

function SettingsSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="h-6 bg-bg-tertiary rounded w-48 mb-4" />
      <div className="space-y-6">
        {[...Array(4)].map((_, i) => (
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
