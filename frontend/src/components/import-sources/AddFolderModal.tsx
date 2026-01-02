/**
 * Modal for adding a folder to an existing import source
 */
import { useState, useEffect } from 'react'
import { useImportProfiles } from '@/hooks/useImportProfiles'
import type { ImportSourceFolderCreate, ImportSourceType, ImportProfile } from '@/types/import-source'

interface AddFolderModalProps {
  isOpen: boolean
  sourceId: string
  sourceType: ImportSourceType
  sourceName: string
  onClose: () => void
  onSubmit: (data: ImportSourceFolderCreate) => void
  isSubmitting: boolean
  error: string | null
}

export function AddFolderModal({
  isOpen,
  sourceType,
  sourceName,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: AddFolderModalProps) {
  const [formData, setFormData] = useState<ImportSourceFolderCreate>({
    name: '',
    enabled: true,
  })
  const [showAdvanced, setShowAdvanced] = useState(false)

  const { data: profilesData } = useImportProfiles()

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        enabled: true,
      })
      setShowAdvanced(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  const canSubmit = () => {
    if (sourceType === 'BULK_FOLDER' && !formData.folder_path?.trim()) return false
    if (sourceType === 'GOOGLE_DRIVE' && !formData.google_drive_url?.trim()) return false
    return true
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Add Folder</h2>
            <p className="text-sm text-text-secondary mt-0.5">
              Add to {sourceName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
            aria-label="Close"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-4 space-y-4">
            {/* Folder location based on source type */}
            {sourceType === 'BULK_FOLDER' && (
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Folder Path <span className="text-accent-danger">*</span>
                </label>
                <input
                  type="text"
                  value={formData.folder_path || ''}
                  onChange={(e) => setFormData({ ...formData, folder_path: e.target.value })}
                  placeholder="/mnt/models/new-folder"
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50 font-mono text-sm"
                  autoFocus
                />
                <p className="text-xs text-text-muted mt-1">
                  Path to the folder containing 3D model files
                </p>
              </div>
            )}

            {sourceType === 'GOOGLE_DRIVE' && (
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Google Drive Folder URL <span className="text-accent-danger">*</span>
                </label>
                <input
                  type="url"
                  value={formData.google_drive_url || ''}
                  onChange={(e) => setFormData({ ...formData, google_drive_url: e.target.value })}
                  placeholder="https://drive.google.com/drive/folders/..."
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  autoFocus
                />
                <p className="text-xs text-text-muted mt-1">
                  URL of the Google Drive folder to import from
                </p>
              </div>
            )}

            {/* Display name */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value || undefined })}
                placeholder="e.g., December 2025 Release"
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
              />
              <p className="text-xs text-text-muted mt-1">
                Optional friendly name for this folder
              </p>
            </div>

            {/* Advanced settings toggle */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary"
            >
              <ChevronIcon className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
              <span>Advanced settings (override source defaults)</span>
            </button>

            {/* Advanced settings */}
            {showAdvanced && (
              <div className="space-y-4 pl-6 border-l-2 border-bg-tertiary">
                {/* Import Profile override */}
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">
                    Import Profile
                  </label>
                  <select
                    value={formData.import_profile_id || ''}
                    onChange={(e) => setFormData({ ...formData, import_profile_id: e.target.value || undefined })}
                    className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  >
                    <option value="">Use source default</option>
                    {profilesData?.items.map((profile: ImportProfile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name} {profile.is_builtin ? '(built-in)' : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Default Designer override */}
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">
                    Default Designer
                  </label>
                  <input
                    type="text"
                    value={formData.default_designer || ''}
                    onChange={(e) => setFormData({ ...formData, default_designer: e.target.value || undefined })}
                    placeholder="Use source default"
                    className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  />
                </div>

                {/* Enabled toggle */}
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-text-primary">Enabled</label>
                    <p className="text-xs text-text-muted">Include in sync operations</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.enabled ?? true}
                      onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-primary"></div>
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-4 mb-4 px-3 py-2 bg-accent-danger/20 border border-accent-danger/50 rounded text-sm text-accent-danger">
              {error}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between p-4 border-t border-bg-tertiary">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting || !canSubmit()}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting && <SpinnerIcon className="w-4 h-4 animate-spin" />}
              {isSubmitting ? 'Adding...' : 'Add Folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
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
