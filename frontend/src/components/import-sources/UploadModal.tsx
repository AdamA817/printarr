/**
 * Upload modal for manual file imports
 * Combines drag-and-drop zone, upload queue, and import profile selection
 */
import { useState, useCallback, useRef } from 'react'
import { UploadZone } from './UploadZone'
import { UploadQueue } from './UploadQueue'
import type { UploadItem, UploadStatus } from './UploadQueue'
import { useImportProfiles } from '@/hooks/useImportProfiles'
import { useSettings } from '@/hooks/useSettings'
import { uploadApi } from '@/services/api'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUploadsComplete?: (count: number) => void
}

// Default max size fallback (500MB)
const DEFAULT_MAX_SIZE_MB = 500

export function UploadModal({ isOpen, onClose, onUploadsComplete }: UploadModalProps) {
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const uploadIdCounter = useRef(0)

  const { data: profilesData } = useImportProfiles()
  const { data: settings } = useSettings()

  // Get max upload size from settings (convert MB to bytes)
  const maxUploadSize = ((settings?.upload_max_size_mb as number) ?? DEFAULT_MAX_SIZE_MB) * 1024 * 1024

  // Upload a file using the real API
  const uploadFile = useCallback(async (id: string, file: File, profileId: string) => {
    // Move to uploading state
    setUploads((prev) =>
      prev.map((u) => (u.id === id ? { ...u, status: 'uploading' as UploadStatus } : u))
    )

    try {
      // Step 1: Upload the file with progress tracking
      const uploadResponse = await uploadApi.uploadFile(file, (progress) => {
        setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, progress } : u)))
      })

      // Store the server upload ID
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id
            ? { ...u, serverUploadId: uploadResponse.upload_id, progress: 100, status: 'processing' as UploadStatus }
            : u
        )
      )

      // Step 2: Process the upload with the selected import profile
      const processResponse = await uploadApi.process(uploadResponse.upload_id, {
        import_profile_id: profileId || undefined,
      })

      // Handle processing result
      if (processResponse.status === 'COMPLETED') {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? {
                  ...u,
                  status: 'complete' as UploadStatus,
                  designId: processResponse.design_id || undefined,
                }
              : u
          )
        )
      } else if (processResponse.status === 'FAILED') {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? {
                  ...u,
                  status: 'error' as UploadStatus,
                  error: processResponse.error_message || 'Processing failed',
                }
              : u
          )
        )
      } else {
        // Unexpected status - treat as error
        console.warn('Unexpected upload status:', processResponse.status)
        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? {
                  ...u,
                  status: 'error' as UploadStatus,
                  error: `Unexpected status: ${processResponse.status}`,
                }
              : u
          )
        )
      }
    } catch (error) {
      // Handle upload or processing error
      const errorMessage = error instanceof Error ? error.message : 'Upload failed'
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id
            ? { ...u, status: 'error' as UploadStatus, error: errorMessage }
            : u
        )
      )
    }
  }, [])

  const handleFilesSelected = useCallback((files: File[]) => {
    const newUploads: UploadItem[] = files.map((file) => ({
      id: `upload-${++uploadIdCounter.current}`,
      file,
      status: 'queued' as UploadStatus,
      progress: 0,
    }))
    setUploads((prev) => [...prev, ...newUploads])

    // Start uploading each file
    newUploads.forEach((upload) => {
      uploadFile(upload.id, upload.file, selectedProfileId)
    })
  }, [uploadFile, selectedProfileId])

  const handleCancel = useCallback(async (id: string) => {
    // Find the upload to check if it has a server ID
    const upload = uploads.find((u) => u.id === id)

    // If upload is in progress on server, try to delete it
    if (upload?.serverUploadId) {
      try {
        await uploadApi.delete(upload.serverUploadId)
      } catch {
        // Ignore errors when canceling
      }
    }

    // Remove from local state
    setUploads((prev) => prev.filter((u) => u.id !== id))
  }, [uploads])

  const handleRetry = useCallback(
    (id: string) => {
      const upload = uploads.find((u) => u.id === id)
      if (!upload) return

      // Reset state and retry
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id
            ? { ...u, status: 'queued' as UploadStatus, progress: 0, error: undefined, serverUploadId: undefined }
            : u
        )
      )
      uploadFile(id, upload.file, selectedProfileId)
    },
    [uploads, uploadFile, selectedProfileId]
  )

  const handleRemove = useCallback((id: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== id))
  }, [])

  const handleClose = () => {
    const completedCount = uploads.filter((u) => u.status === 'complete').length
    if (completedCount > 0 && onUploadsComplete) {
      onUploadsComplete(completedCount)
    }
    setUploads([])
    onClose()
  }

  const hasActiveUploads = uploads.some(
    (u) => u.status === 'queued' || u.status === 'uploading' || u.status === 'processing'
  )

  const completedCount = uploads.filter((u) => u.status === 'complete').length
  const errorCount = uploads.filter((u) => u.status === 'error').length

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={hasActiveUploads ? undefined : handleClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Upload Files</h2>
            <p className="text-sm text-text-muted mt-0.5">
              Upload 3D model files to import into your catalog
            </p>
          </div>
          <button
            onClick={handleClose}
            disabled={hasActiveUploads}
            className="p-2 text-text-muted hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={hasActiveUploads ? 'Wait for uploads to complete' : 'Close'}
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Import profile selection */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">
              Import Profile
            </label>
            <select
              value={selectedProfileId}
              onChange={(e) => setSelectedProfileId(e.target.value)}
              className="w-full bg-bg-tertiary text-text-primary rounded-lg px-3 py-2 border border-bg-tertiary focus:outline-none focus:ring-2 focus:ring-accent-primary"
            >
              <option value="">Select a profile...</option>
              {profilesData?.items.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                  {profile.is_builtin ? ' (Built-in)' : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-text-muted mt-1">
              The profile determines how uploaded files are organized and processed
            </p>
          </div>

          {/* Upload zone */}
          <UploadZone
            onFilesSelected={handleFilesSelected}
            disabled={!selectedProfileId}
            accept={['.stl', '.obj', '.3mf', '.step', '.stp', '.zip', '.rar', '.7z']}
            maxSize={maxUploadSize}
          />

          {/* Upload queue */}
          <UploadQueue
            items={uploads}
            onCancel={handleCancel}
            onRetry={handleRetry}
            onRemove={handleRemove}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-bg-tertiary">
          <div className="text-sm text-text-muted">
            {uploads.length === 0 ? (
              'No files selected'
            ) : (
              <>
                {completedCount > 0 && (
                  <span className="text-accent-success">{completedCount} completed</span>
                )}
                {completedCount > 0 && errorCount > 0 && ' · '}
                {errorCount > 0 && <span className="text-accent-danger">{errorCount} failed</span>}
                {(completedCount > 0 || errorCount > 0) && hasActiveUploads && ' · '}
                {hasActiveUploads && (
                  <span>
                    {uploads.filter((u) => u.status !== 'complete' && u.status !== 'error').length}{' '}
                    in progress
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex gap-3">
            {uploads.length > 0 && !hasActiveUploads && (
              <button
                onClick={() => setUploads([])}
                className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                Clear All
              </button>
            )}
            <button
              onClick={handleClose}
              disabled={hasActiveUploads}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {hasActiveUploads ? 'Uploading...' : 'Done'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
