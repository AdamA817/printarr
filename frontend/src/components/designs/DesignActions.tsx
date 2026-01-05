import { useState } from 'react'
import type { DesignStatus } from '@/types/design'
import { useWantDesign, useDownloadDesign, useCancelDownload } from '@/hooks/useDesigns'

interface DesignActionsProps {
  designId: string
  status: DesignStatus
  size?: 'sm' | 'md'
  variant?: 'icon' | 'button'
  onActionStart?: () => void
  onActionComplete?: () => void
  onError?: (error: Error) => void
}

// Icon components
function HeartIcon({ className }: { className?: string }) {
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
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
    </svg>
  )
}

function DownloadIcon({ className }: { className?: string }) {
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
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`animate-spin ${className}`}
    >
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" strokeOpacity="1" />
    </svg>
  )
}

function XIcon({ className }: { className?: string }) {
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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
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

function FolderIcon({ className }: { className?: string }) {
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
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
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
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  )
}

export function DesignActions({
  designId,
  status,
  size = 'md',
  variant = 'icon',
  onActionStart,
  onActionComplete,
  onError,
}: DesignActionsProps) {
  const [isLoading, setIsLoading] = useState(false)
  const wantDesign = useWantDesign()
  const downloadDesign = useDownloadDesign()
  const cancelDownload = useCancelDownload()

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
  }

  const buttonSizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm',
  }

  const handleAction = async (
    e: React.MouseEvent,
    action: () => Promise<unknown>
  ) => {
    e.preventDefault()
    e.stopPropagation()

    if (isLoading) return

    setIsLoading(true)
    onActionStart?.()

    try {
      await action()
      onActionComplete?.()
    } catch (error) {
      console.error('Action failed:', error)
      onError?.(error instanceof Error ? error : new Error('Action failed'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleWant = (e: React.MouseEvent) => {
    handleAction(e, () => wantDesign.mutateAsync(designId))
  }

  const handleDownload = (e: React.MouseEvent) => {
    handleAction(e, () => downloadDesign.mutateAsync(designId))
  }

  const handleCancel = (e: React.MouseEvent) => {
    handleAction(e, () => cancelDownload.mutateAsync(designId))
  }

  const handleRetry = (e: React.MouseEvent) => {
    // Retry a failed download by re-triggering the download workflow
    handleAction(e, () => downloadDesign.mutateAsync(designId))
  }

  // Render based on status
  switch (status) {
    case 'DISCOVERED':
      return variant === 'icon' ? (
        <button
          onClick={handleWant}
          disabled={isLoading}
          className="p-1.5 rounded-full bg-bg-tertiary hover:bg-accent-primary/20 text-text-secondary hover:text-accent-primary transition-colors disabled:opacity-50"
          title="Mark as Wanted"
        >
          {isLoading ? (
            <LoadingSpinner className={sizeClasses[size]} />
          ) : (
            <HeartIcon className={sizeClasses[size]} />
          )}
        </button>
      ) : (
        <button
          onClick={handleWant}
          disabled={isLoading}
          className={`${buttonSizeClasses[size]} rounded bg-accent-primary hover:bg-accent-primary/80 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5 min-w-[90px] justify-center`}
        >
          {isLoading ? (
            <>
              <LoadingSpinner className={sizeClasses[size]} />
              Marking...
            </>
          ) : (
            <>
              <HeartIcon className={sizeClasses[size]} />
              Want
            </>
          )}
        </button>
      )

    case 'WANTED':
      return variant === 'icon' ? (
        <button
          onClick={handleDownload}
          disabled={isLoading}
          className="p-1.5 rounded-full bg-accent-warning/20 hover:bg-accent-warning/30 text-accent-warning transition-colors disabled:opacity-50"
          title="Download Now"
        >
          {isLoading ? (
            <LoadingSpinner className={sizeClasses[size]} />
          ) : (
            <DownloadIcon className={sizeClasses[size]} />
          )}
        </button>
      ) : (
        <button
          onClick={handleDownload}
          disabled={isLoading}
          className={`${buttonSizeClasses[size]} rounded bg-accent-warning hover:bg-accent-warning/80 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5 min-w-[90px] justify-center`}
        >
          {isLoading ? (
            <>
              <LoadingSpinner className={sizeClasses[size]} />
              Starting...
            </>
          ) : (
            <>
              <DownloadIcon className={sizeClasses[size]} />
              Download
            </>
          )}
        </button>
      )

    case 'DOWNLOADING':
      return variant === 'icon' ? (
        <button
          onClick={handleCancel}
          disabled={isLoading}
          className="p-1.5 rounded-full bg-accent-primary/20 text-accent-primary hover:bg-accent-danger/20 hover:text-accent-danger transition-colors disabled:opacity-50"
          title="Cancel Download"
        >
          {isLoading ? (
            <LoadingSpinner className={sizeClasses[size]} />
          ) : (
            <XIcon className={sizeClasses[size]} />
          )}
        </button>
      ) : (
        <button
          onClick={handleCancel}
          disabled={isLoading}
          className={`${buttonSizeClasses[size]} rounded bg-accent-danger hover:bg-accent-danger/80 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5 min-w-[90px] justify-center`}
        >
          {isLoading ? (
            <>
              <LoadingSpinner className={sizeClasses[size]} />
              Cancelling...
            </>
          ) : (
            <>
              <XIcon className={sizeClasses[size]} />
              Cancel
            </>
          )}
        </button>
      )

    case 'DOWNLOADED':
      return variant === 'icon' ? (
        <span
          className="p-1.5 rounded-full bg-accent-success/20 text-accent-success"
          title="Downloaded"
        >
          <CheckIcon className={sizeClasses[size]} />
        </span>
      ) : (
        <span
          className={`${buttonSizeClasses[size]} rounded bg-accent-success/20 text-accent-success font-medium flex items-center gap-1.5`}
        >
          <CheckIcon className={sizeClasses[size]} />
          Downloaded
        </span>
      )

    case 'ORGANIZED':
      return variant === 'icon' ? (
        <span
          className="p-1.5 rounded-full bg-accent-success/20 text-accent-success"
          title="In Library"
        >
          <FolderIcon className={sizeClasses[size]} />
        </span>
      ) : (
        <span
          className={`${buttonSizeClasses[size]} rounded bg-accent-success/20 text-accent-success font-medium flex items-center gap-1.5`}
        >
          <FolderIcon className={sizeClasses[size]} />
          In Library
        </span>
      )

    case 'FAILED':
      return variant === 'icon' ? (
        <button
          onClick={handleRetry}
          disabled={isLoading}
          className="p-1.5 rounded-full bg-accent-danger/20 hover:bg-accent-danger/30 text-accent-danger transition-colors disabled:opacity-50"
          title="Retry Download"
        >
          {isLoading ? (
            <LoadingSpinner className={sizeClasses[size]} />
          ) : (
            <RefreshIcon className={sizeClasses[size]} />
          )}
        </button>
      ) : (
        <button
          onClick={handleRetry}
          disabled={isLoading}
          className={`${buttonSizeClasses[size]} rounded bg-accent-danger hover:bg-accent-danger/80 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5 min-w-[90px] justify-center`}
        >
          {isLoading ? (
            <>
              <LoadingSpinner className={sizeClasses[size]} />
              Retrying...
            </>
          ) : (
            <>
              <RefreshIcon className={sizeClasses[size]} />
              Retry
            </>
          )}
        </button>
      )

    default:
      return null
  }
}
