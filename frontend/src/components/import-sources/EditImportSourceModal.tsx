/**
 * Modal for editing an existing import source
 */
import { useState, useEffect } from 'react'
import { useImportProfiles } from '@/hooks/useImportProfiles'
import type { ImportSource, ImportSourceUpdate, ImportProfile } from '@/types/import-source'

interface EditImportSourceModalProps {
  isOpen: boolean
  source: ImportSource | null
  onClose: () => void
  onSubmit: (data: ImportSourceUpdate) => void
  isSubmitting: boolean
  error: string | null
}

export function EditImportSourceModal({
  isOpen,
  source,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: EditImportSourceModalProps) {
  const [formData, setFormData] = useState<ImportSourceUpdate>({})

  const { data: profilesData } = useImportProfiles()

  // Initialize form data when source changes
  useEffect(() => {
    if (source) {
      setFormData({
        name: source.name,
        google_drive_url: source.google_drive_url || undefined,
        folder_path: source.folder_path || undefined,
        import_profile_id: source.import_profile_id || undefined,
        default_designer: source.default_designer || undefined,
        default_tags: source.default_tags || undefined,
        sync_enabled: source.sync_enabled,
        sync_interval_hours: source.sync_interval_hours,
      })
    }
  }, [source])

  if (!isOpen || !source) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  const getSourceTypeLabel = () => {
    switch (source.source_type) {
      case 'GOOGLE_DRIVE':
        return 'Google Drive'
      case 'BULK_FOLDER':
        return 'Bulk Folder'
      case 'UPLOAD':
        return 'Upload'
      default:
        return source.source_type
    }
  }

  const canSubmit = () => {
    if (!formData.name?.trim()) return false
    if (source.source_type === 'BULK_FOLDER' && !formData.folder_path?.trim()) return false
    if (source.source_type === 'GOOGLE_DRIVE' && !formData.google_drive_url?.trim()) return false
    return true
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Edit Import Source</h2>
            <p className="text-sm text-text-secondary mt-0.5">
              {getSourceTypeLabel()} source
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
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Name <span className="text-accent-danger">*</span>
              </label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="My 3D Models"
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                autoFocus
              />
            </div>

            {/* Bulk Folder specific */}
            {source.source_type === 'BULK_FOLDER' && (
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Folder Path <span className="text-accent-danger">*</span>
                </label>
                <input
                  type="text"
                  value={formData.folder_path || ''}
                  onChange={(e) => setFormData({ ...formData, folder_path: e.target.value })}
                  placeholder="/mnt/models/incoming"
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50 font-mono text-sm"
                />
                <p className="text-xs text-text-muted mt-1">
                  Path to the folder containing 3D model files or design folders
                </p>
              </div>
            )}

            {/* Google Drive specific */}
            {source.source_type === 'GOOGLE_DRIVE' && (
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
                />
                <p className="text-xs text-text-muted mt-1">
                  URL of the Google Drive folder to import from
                </p>
              </div>
            )}

            {/* Divider */}
            <div className="border-t border-bg-tertiary pt-4">
              <h3 className="text-sm font-medium text-text-primary mb-3">Import Settings</h3>
            </div>

            {/* Import Profile */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Import Profile
              </label>
              <select
                value={formData.import_profile_id || ''}
                onChange={(e) => setFormData({ ...formData, import_profile_id: e.target.value || undefined })}
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
              >
                <option value="">Default (Standard)</option>
                {profilesData?.items.map((profile: ImportProfile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} {profile.is_builtin ? '(built-in)' : ''}
                  </option>
                ))}
              </select>
              <p className="text-xs text-text-muted mt-1">
                Controls how designs are detected and organized
              </p>
            </div>

            {/* Default Designer */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Default Designer
              </label>
              <input
                type="text"
                value={formData.default_designer || ''}
                onChange={(e) => setFormData({ ...formData, default_designer: e.target.value || undefined })}
                placeholder="Optional"
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
              />
              <p className="text-xs text-text-muted mt-1">
                Applied to imported designs if no designer is detected
              </p>
            </div>

            {/* Sync Settings - only for non-upload sources */}
            {source.source_type !== 'UPLOAD' && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-text-primary">Auto Sync</label>
                    <p className="text-xs text-text-muted">Automatically check for new files</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.sync_enabled ?? false}
                      onChange={(e) => setFormData({ ...formData, sync_enabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-primary"></div>
                  </label>
                </div>

                {formData.sync_enabled && (
                  <div>
                    <label className="block text-sm font-medium text-text-primary mb-1">
                      Sync Interval
                    </label>
                    <select
                      value={formData.sync_interval_hours ?? 1}
                      onChange={(e) => setFormData({ ...formData, sync_interval_hours: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                    >
                      <option value={1}>Every hour</option>
                      <option value={6}>Every 6 hours</option>
                      <option value={12}>Every 12 hours</option>
                      <option value={24}>Every day</option>
                      <option value={168}>Every week</option>
                    </select>
                  </div>
                )}
              </>
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
              {isSubmitting ? 'Saving...' : 'Save Changes'}
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

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" strokeWidth={2} strokeDasharray="60" strokeDashoffset="20" />
    </svg>
  )
}
