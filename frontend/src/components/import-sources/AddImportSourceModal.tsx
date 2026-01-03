/**
 * Modal for adding a new import source with wizard steps
 */
import { useState, useEffect } from 'react'
import { useImportProfiles } from '@/hooks/useImportProfiles'
import { useGoogleOAuthStatus } from '@/hooks/useGoogleOAuth'
import { GoogleConnectCard } from './GoogleConnectCard'
import type { ImportSourceCreate, ImportSourceType, ImportProfile } from '@/types/import-source'

interface AddImportSourceModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: ImportSourceCreate) => void
  isSubmitting: boolean
  error: string | null
}

type WizardStep = 'type' | 'configure' | 'settings'

export function AddImportSourceModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: AddImportSourceModalProps) {
  const [step, setStep] = useState<WizardStep>('type')
  const [formData, setFormData] = useState<ImportSourceCreate>({
    name: '',
    source_type: 'BULK_FOLDER',
    folder_path: '',
    sync_enabled: true,
    sync_interval_hours: 1,
  })
  const [selectedCredentialsId, setSelectedCredentialsId] = useState<string | null>(null)

  const { data: profilesData } = useImportProfiles()
  const { data: oauthStatus } = useGoogleOAuthStatus()

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep('type')
      setFormData({
        name: '',
        source_type: 'BULK_FOLDER',
        folder_path: '',
        sync_enabled: true,
        sync_interval_hours: 1,
      })
      setSelectedCredentialsId(null)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleTypeSelect = (type: ImportSourceType) => {
    setFormData((prev) => ({
      ...prev,
      source_type: type,
      // Clear type-specific fields
      google_drive_url: type === 'GOOGLE_DRIVE' ? '' : undefined,
      folder_path: type === 'BULK_FOLDER' ? '' : undefined,
    }))
    setStep('configure')
  }

  const handleBack = () => {
    if (step === 'configure') setStep('type')
    else if (step === 'settings') setStep('configure')
  }

  const handleNext = () => {
    if (step === 'configure') setStep('settings')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Include google_credentials_id if a Google account was selected
    const submitData = {
      ...formData,
      ...(selectedCredentialsId && { google_credentials_id: selectedCredentialsId }),
    }
    onSubmit(submitData)
  }

  const canProceedFromConfigure = () => {
    if (!formData.name.trim()) return false
    if (formData.source_type === 'BULK_FOLDER' && !formData.folder_path?.trim()) return false
    if (formData.source_type === 'GOOGLE_DRIVE') {
      if (!formData.google_drive_url?.trim()) return false
      // Only require credentials if OAuth is configured (for private folders)
      // API key mode (public folders) doesn't need credentials
      if (oauthStatus?.configured && !selectedCredentialsId) return false
    }
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
            <h2 className="text-lg font-semibold text-text-primary">Add Import Source</h2>
            <p className="text-sm text-text-secondary mt-0.5">
              {step === 'type' && 'Select the type of import source'}
              {step === 'configure' && 'Configure source details'}
              {step === 'settings' && 'Set import preferences'}
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

        {/* Progress indicator */}
        <div className="px-4 pt-4">
          <div className="flex items-center gap-2">
            <StepIndicator number={1} label="Type" active={step === 'type'} completed={step !== 'type'} />
            <div className="flex-1 h-0.5 bg-bg-tertiary" />
            <StepIndicator number={2} label="Configure" active={step === 'configure'} completed={step === 'settings'} />
            <div className="flex-1 h-0.5 bg-bg-tertiary" />
            <StepIndicator number={3} label="Settings" active={step === 'settings'} completed={false} />
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Step 1: Select Type */}
          {step === 'type' && (
            <div className="p-4 space-y-3">
              <SourceTypeOption
                type="BULK_FOLDER"
                icon={<FolderIcon className="w-8 h-8" />}
                title="Bulk Folder"
                description="Monitor a local folder for new designs"
                selected={formData.source_type === 'BULK_FOLDER'}
                onClick={() => handleTypeSelect('BULK_FOLDER')}
              />
              <SourceTypeOption
                type="GOOGLE_DRIVE"
                icon={<GoogleDriveIcon className="w-8 h-8" />}
                title="Google Drive"
                description={oauthStatus?.api_key_configured && !oauthStatus?.configured
                  ? "Import from public Google Drive folders"
                  : "Import from a Google Drive folder"}
                selected={formData.source_type === 'GOOGLE_DRIVE'}
                onClick={() => handleTypeSelect('GOOGLE_DRIVE')}
                disabled={!oauthStatus?.configured && !oauthStatus?.api_key_configured}
                disabledReason={!oauthStatus?.configured && !oauthStatus?.api_key_configured ? 'Not configured' : undefined}
              />
              <SourceTypeOption
                type="UPLOAD"
                icon={<UploadIcon className="w-8 h-8" />}
                title="Direct Upload"
                description="Upload files directly via browser"
                selected={formData.source_type === 'UPLOAD'}
                onClick={() => handleTypeSelect('UPLOAD')}
                disabled
                disabledReason="Coming soon"
              />
            </div>
          )}

          {/* Step 2: Configure */}
          {step === 'configure' && (
            <div className="p-4 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Name <span className="text-accent-danger">*</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My 3D Models"
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  autoFocus
                />
              </div>

              {/* Bulk Folder specific */}
              {formData.source_type === 'BULK_FOLDER' && (
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
              {formData.source_type === 'GOOGLE_DRIVE' && (
                <div className="space-y-4">
                  {/* Google account connection - only show if OAuth is configured */}
                  {oauthStatus?.configured && (
                    <GoogleConnectCard
                      selectedCredentialsId={selectedCredentialsId || undefined}
                      onSelectCredentials={(id) => setSelectedCredentialsId(id)}
                    />
                  )}

                  {/* API key mode notice */}
                  {!oauthStatus?.configured && oauthStatus?.api_key_configured && (
                    <div className="p-3 bg-accent-warning/10 border border-accent-warning/30 rounded-lg">
                      <p className="text-sm text-accent-warning font-medium">Public Folders Only</p>
                      <p className="text-xs text-text-secondary mt-1">
                        Using API key mode. Only publicly shared Google Drive folders are supported.
                        Set up OAuth credentials to access private folders.
                      </p>
                    </div>
                  )}

                  {/* Google Drive URL */}
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
                      disabled={oauthStatus?.configured && !selectedCredentialsId}
                    />
                    <p className="text-xs text-text-muted mt-1">
                      {oauthStatus?.configured
                        ? 'Paste the URL of a Google Drive folder you want to import from'
                        : 'Paste the URL of a publicly shared Google Drive folder'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Settings */}
          {step === 'settings' && (
            <div className="p-4 space-y-4">
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

              {/* Sync Settings */}
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-text-primary">Auto Sync</label>
                  <p className="text-xs text-text-muted">Automatically check for new files</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.sync_enabled}
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
                    value={formData.sync_interval_hours}
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
            </div>
          )}

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
              onClick={step === 'type' ? onClose : handleBack}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              {step === 'type' ? 'Cancel' : 'Back'}
            </button>

            {step === 'configure' && (
              <button
                type="button"
                onClick={handleNext}
                disabled={!canProceedFromConfigure()}
                className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            )}

            {step === 'settings' && (
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting && <SpinnerIcon className="w-4 h-4 animate-spin" />}
                {isSubmitting ? 'Creating...' : 'Create Source'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}

// =============================================================================
// Sub-components
// =============================================================================

interface StepIndicatorProps {
  number: number
  label: string
  active: boolean
  completed: boolean
}

function StepIndicator({ number, label, active, completed }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium ${
          active
            ? 'bg-accent-primary text-white'
            : completed
            ? 'bg-accent-success text-white'
            : 'bg-bg-tertiary text-text-muted'
        }`}
      >
        {completed ? <CheckIcon className="w-4 h-4" /> : number}
      </div>
      <span className={`text-sm ${active ? 'text-text-primary font-medium' : 'text-text-muted'}`}>
        {label}
      </span>
    </div>
  )
}

interface SourceTypeOptionProps {
  type: ImportSourceType
  icon: React.ReactNode
  title: string
  description: string
  selected: boolean
  onClick: () => void
  disabled?: boolean
  disabledReason?: string
}

function SourceTypeOption({
  icon,
  title,
  description,
  selected,
  onClick,
  disabled,
  disabledReason,
}: SourceTypeOptionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full p-4 rounded-lg border-2 text-left flex items-start gap-4 transition-colors ${
        disabled
          ? 'opacity-50 cursor-not-allowed border-bg-tertiary bg-bg-tertiary/50'
          : selected
          ? 'border-accent-primary bg-accent-primary/10'
          : 'border-bg-tertiary hover:border-text-muted bg-bg-tertiary/50'
      }`}
    >
      <div className="text-text-secondary">{icon}</div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text-primary">{title}</span>
          {disabled && disabledReason && (
            <span className="text-xs bg-accent-warning/20 text-accent-warning px-2 py-0.5 rounded">
              {disabledReason}
            </span>
          )}
        </div>
        <p className="text-sm text-text-secondary mt-0.5">{description}</p>
      </div>
    </button>
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

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
      />
    </svg>
  )
}

function GoogleDriveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7.71 3.5L1.15 15l3.43 5.95L11.15 9.5 7.71 3.5zm2.85 0l6.57 11.43H22.7L16.14 3.5H10.56zm4.01 12.15L11.15 21h11.55l3.43-5.35H14.57z" />
    </svg>
  )
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
      />
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
