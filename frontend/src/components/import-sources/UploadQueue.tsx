/**
 * Upload queue component showing pending/in-progress/completed uploads
 */

export type UploadStatus = 'queued' | 'uploading' | 'processing' | 'complete' | 'error'

export interface UploadItem {
  id: string // Client-side ID for React key
  file: File
  status: UploadStatus
  progress: number // 0-100
  error?: string
  serverUploadId?: string // Server-side upload ID (set after upload completes)
  designId?: string // Design ID if processing completed successfully
}

interface UploadQueueProps {
  items: UploadItem[]
  onCancel: (id: string) => void
  onRetry: (id: string) => void
  onRemove: (id: string) => void
}

export function UploadQueue({ items, onCancel, onRetry, onRemove }: UploadQueueProps) {
  if (items.length === 0) return null

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  const getStatusIcon = (status: UploadStatus) => {
    switch (status) {
      case 'queued':
        return <QueuedIcon className="w-5 h-5 text-text-muted" />
      case 'uploading':
        return <SpinnerIcon className="w-5 h-5 text-accent-primary animate-spin" />
      case 'processing':
        return <SpinnerIcon className="w-5 h-5 text-accent-warning animate-spin" />
      case 'complete':
        return <CheckIcon className="w-5 h-5 text-accent-success" />
      case 'error':
        return <ErrorIcon className="w-5 h-5 text-accent-danger" />
    }
  }

  const getStatusText = (item: UploadItem) => {
    switch (item.status) {
      case 'queued':
        return 'Queued'
      case 'uploading':
        return `Uploading... ${item.progress}%`
      case 'processing':
        return 'Processing...'
      case 'complete':
        return 'Complete'
      case 'error':
        return item.error || 'Failed'
    }
  }

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-bg-tertiary">
        <h3 className="font-medium text-text-primary">
          Uploads ({items.length})
        </h3>
      </div>

      <div className="divide-y divide-bg-tertiary">
        {items.map((item) => (
          <div key={item.id} className="px-4 py-3">
            <div className="flex items-center gap-3">
              {/* Status icon */}
              <div className="flex-shrink-0">{getStatusIcon(item.status)}</div>

              {/* File info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary truncate">{item.file.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-text-muted">{formatFileSize(item.file.size)}</span>
                  <span className="text-xs text-text-muted">•</span>
                  <span
                    className={`text-xs ${
                      item.status === 'error'
                        ? 'text-accent-danger'
                        : item.status === 'complete'
                        ? 'text-accent-success'
                        : 'text-text-muted'
                    }`}
                  >
                    {getStatusText(item)}
                  </span>
                </div>

                {/* Progress bar */}
                {(item.status === 'uploading' || item.status === 'processing') && (
                  <div className="mt-2 h-1 bg-bg-tertiary rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        item.status === 'processing' ? 'bg-accent-warning' : 'bg-accent-primary'
                      }`}
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex-shrink-0">
                {item.status === 'queued' && (
                  <button
                    onClick={() => onCancel(item.id)}
                    className="p-1 text-text-muted hover:text-accent-danger transition-colors"
                    title="Cancel"
                  >
                    <CloseIcon className="w-4 h-4" />
                  </button>
                )}
                {item.status === 'uploading' && (
                  <button
                    onClick={() => onCancel(item.id)}
                    className="p-1 text-text-muted hover:text-accent-danger transition-colors"
                    title="Cancel"
                  >
                    <CloseIcon className="w-4 h-4" />
                  </button>
                )}
                {item.status === 'error' && (
                  <button
                    onClick={() => onRetry(item.id)}
                    className="p-1 text-text-muted hover:text-accent-primary transition-colors"
                    title="Retry"
                  >
                    <RetryIcon className="w-4 h-4" />
                  </button>
                )}
                {item.status === 'complete' && (
                  <button
                    onClick={() => onRemove(item.id)}
                    className="p-1 text-text-muted hover:text-text-primary transition-colors"
                    title="Remove"
                  >
                    <CloseIcon className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function QueuedIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
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

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function ErrorIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  )
}
