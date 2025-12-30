import { useState, useEffect, useMemo } from 'react'
import { useLibrarySettings, useUpdateSetting } from '@/hooks/useSettings'
import {
  TEMPLATE_VARIABLES,
  DEFAULT_FOLDER_TEMPLATE,
} from '@/types/settings'

// Example values for preview
const EXAMPLE_VALUES: Record<string, string> = {
  '{designer}': 'JohnDoe',
  '{channel}': '3DPrintHub',
  '{title}': 'Thor_Helmet',
  '{date}': '2025-01-15',
  '{year}': '2025',
  '{month}': '01',
}

function generatePreview(template: string): string {
  let preview = template
  for (const [variable, value] of Object.entries(EXAMPLE_VALUES)) {
    preview = preview.replaceAll(variable, value)
  }
  return preview
}

function validateTemplate(template: string): string | null {
  if (!template.includes('{title}')) {
    return 'Template must contain {title}'
  }
  return null
}

export function LibrarySettings() {
  const { settings, isLoading } = useLibrarySettings()
  const updateSetting = useUpdateSetting()

  // Local state for form
  const [folderTemplate, setFolderTemplate] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    if (settings.folder_template) {
      setFolderTemplate(settings.folder_template)
    }
  }, [settings.folder_template])

  // Track changes
  useEffect(() => {
    setHasChanges(folderTemplate !== settings.folder_template)
  }, [folderTemplate, settings.folder_template])

  // Preview with debouncing effect built into useMemo
  const preview = useMemo(() => generatePreview(folderTemplate), [folderTemplate])
  const validationError = useMemo(() => validateTemplate(folderTemplate), [folderTemplate])

  const handleSave = async () => {
    if (validationError) return

    setSaveStatus('saving')
    try {
      await updateSetting.mutateAsync({
        key: 'folder_template',
        value: folderTemplate,
      })
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save folder template:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  const handleReset = () => {
    setFolderTemplate(DEFAULT_FOLDER_TEMPLATE)
  }

  if (isLoading) {
    return <LibrarySettingsSkeleton />
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4">
        Library Settings
      </h3>

      <div className="space-y-6">
        {/* Folder Template */}
        <div>
          <label
            htmlFor="folder-template"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Folder Template
          </label>
          <p className="text-sm text-text-secondary mb-3">
            Configure how design files are organized in your library. Use template variables to create a dynamic folder structure.
          </p>

          <div className="flex gap-2">
            <input
              id="folder-template"
              type="text"
              value={folderTemplate}
              onChange={(e) => setFolderTemplate(e.target.value)}
              className={`flex-1 px-3 py-2 rounded bg-bg-tertiary text-text-primary border ${
                validationError
                  ? 'border-accent-danger focus:ring-accent-danger'
                  : 'border-transparent focus:ring-accent-primary'
              } focus:outline-none focus:ring-2`}
              placeholder="{designer}/{title}"
            />
            <button
              onClick={handleReset}
              className="px-3 py-2 rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
              title="Reset to default"
            >
              <ResetIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Validation error */}
          {validationError && (
            <p className="mt-2 text-sm text-accent-danger">{validationError}</p>
          )}

          {/* Preview */}
          <div className="mt-3 p-3 bg-bg-tertiary rounded">
            <span className="text-xs text-text-muted uppercase tracking-wide">Preview</span>
            <p className="mt-1 text-sm text-text-primary font-mono">
              /{preview}
            </p>
          </div>
        </div>

        {/* Available Variables */}
        <div>
          <h4 className="text-sm font-medium text-text-primary mb-2">
            Available Variables
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {TEMPLATE_VARIABLES.map((variable) => (
              <button
                key={variable.name}
                onClick={() => setFolderTemplate((t) => t + variable.name)}
                className="text-left p-2 rounded bg-bg-tertiary hover:bg-bg-primary transition-colors group"
              >
                <code className="text-accent-primary text-sm">{variable.name}</code>
                <p className="text-xs text-text-muted mt-0.5 group-hover:text-text-secondary">
                  {variable.description}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!validationError || saveStatus === 'saving'}
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

// Icon components
function ResetIcon({ className }: { className?: string }) {
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

function LibrarySettingsSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="h-6 bg-bg-tertiary rounded w-40 mb-4" />
      <div className="space-y-6">
        <div>
          <div className="h-4 bg-bg-tertiary rounded w-32 mb-2" />
          <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-3" />
          <div className="h-10 bg-bg-tertiary rounded w-full" />
          <div className="mt-3 h-16 bg-bg-tertiary rounded" />
        </div>
        <div>
          <div className="h-4 bg-bg-tertiary rounded w-40 mb-2" />
          <div className="grid grid-cols-3 gap-2">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-14 bg-bg-tertiary rounded" />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
