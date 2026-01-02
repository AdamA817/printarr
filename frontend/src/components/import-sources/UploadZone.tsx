/**
 * Drag-and-drop file upload zone component
 */
import { useState, useRef, useCallback } from 'react'

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
  accept?: string[]
  maxSize?: number // in bytes
}

const DEFAULT_ACCEPT = ['.stl', '.3mf', '.obj', '.step', '.zip', '.rar', '.7z']
const DEFAULT_MAX_SIZE = 500 * 1024 * 1024 // 500MB

export function UploadZone({
  onFilesSelected,
  disabled = false,
  accept = DEFAULT_ACCEPT,
  maxSize = DEFAULT_MAX_SIZE,
}: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  const validateFiles = useCallback(
    (files: File[]): { valid: File[]; errors: string[] } => {
      const valid: File[] = []
      const errors: string[] = []

      for (const file of files) {
        // Check file extension
        const ext = '.' + file.name.split('.').pop()?.toLowerCase()
        if (!accept.some((a) => a.toLowerCase() === ext)) {
          errors.push(`${file.name}: Unsupported file type`)
          continue
        }

        // Check file size
        if (file.size > maxSize) {
          errors.push(`${file.name}: File too large (max ${formatFileSize(maxSize)})`)
          continue
        }

        valid.push(file)
      }

      return { valid, errors }
    },
    [accept, maxSize]
  )

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return

      const fileArray = Array.from(files)
      const { valid, errors } = validateFiles(fileArray)

      if (errors.length > 0) {
        setError(errors.join('\n'))
        setTimeout(() => setError(null), 5000)
      }

      if (valid.length > 0) {
        onFilesSelected(valid)
      }
    },
    [validateFiles, onFilesSelected]
  )

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set dragging to false if we're leaving the drop zone entirely
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      if (disabled) return
      handleFiles(e.dataTransfer.files)
    },
    [disabled, handleFiles]
  )

  const handleClick = () => {
    if (disabled) return
    inputRef.current?.click()
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
    // Reset input so the same file can be selected again
    e.target.value = ''
  }

  return (
    <div className="space-y-2">
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${
            disabled
              ? 'border-bg-tertiary bg-bg-tertiary/50 cursor-not-allowed opacity-50'
              : isDragging
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-bg-tertiary hover:border-text-muted bg-bg-secondary'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept.join(',')}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />

        <div className="flex flex-col items-center gap-3">
          <div
            className={`w-16 h-16 rounded-full flex items-center justify-center ${
              isDragging ? 'bg-accent-primary/20 text-accent-primary' : 'bg-bg-tertiary text-text-muted'
            }`}
          >
            <UploadIcon className="w-8 h-8" />
          </div>

          <div>
            <p className="text-text-primary font-medium">
              {isDragging ? 'Drop files here' : 'Drag files here or click to browse'}
            </p>
            <p className="text-sm text-text-muted mt-1">
              Supported: {accept.join(', ')}
            </p>
            <p className="text-sm text-text-muted">Max size: {formatFileSize(maxSize)}</p>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-3 text-sm text-accent-danger whitespace-pre-line">
          {error}
        </div>
      )}
    </div>
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
