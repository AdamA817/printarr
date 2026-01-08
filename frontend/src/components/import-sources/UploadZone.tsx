/**
 * Drag-and-drop file upload zone component with folder support
 */
import { useState, useRef, useCallback } from 'react'
import JSZip from 'jszip'

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
  accept?: string[]
  maxSize?: number // in bytes
  allowFolderUpload?: boolean // Enable folder mode toggle
}

type UploadMode = 'files' | 'folder'

const DEFAULT_ACCEPT = ['.stl', '.3mf', '.obj', '.step', '.zip', '.rar', '.7z']
const DEFAULT_MAX_SIZE = 500 * 1024 * 1024 // 500MB

export function UploadZone({
  onFilesSelected,
  disabled = false,
  accept = DEFAULT_ACCEPT,
  maxSize = DEFAULT_MAX_SIZE,
  allowFolderUpload = true,
}: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadMode, setUploadMode] = useState<UploadMode>('files')
  const [isCreatingZip, setIsCreatingZip] = useState(false)
  const [zipProgress, setZipProgress] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  /**
   * Create a zip file from folder contents
   */
  const createZipFromFolder = useCallback(
    async (files: FileList): Promise<File | null> => {
      if (files.length === 0) return null

      setIsCreatingZip(true)
      setZipProgress(0)
      setError(null)

      try {
        const zip = new JSZip()

        // Get folder name from first file's path
        const firstPath = (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath
        if (!firstPath) {
          throw new Error('No folder path information available')
        }
        const folderName = firstPath.split('/')[0]

        // Calculate total size for progress
        let totalSize = 0
        let processedSize = 0
        for (const file of Array.from(files)) {
          totalSize += file.size
        }

        // Check total size
        if (totalSize > maxSize) {
          throw new Error(`Folder size (${formatFileSize(totalSize)}) exceeds maximum (${formatFileSize(maxSize)})`)
        }

        // Add each file to the zip
        for (const file of Array.from(files)) {
          const fileWithPath = file as File & { webkitRelativePath?: string }
          if (!fileWithPath.webkitRelativePath) continue

          // Keep full path including root folder name
          const relativePath = fileWithPath.webkitRelativePath
          zip.file(relativePath, file)

          processedSize += file.size
          setZipProgress(Math.round((processedSize / totalSize) * 50)) // First 50% is adding files
        }

        // Generate the zip blob
        const blob = await zip.generateAsync(
          { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 1 } },
          (metadata) => {
            // Second 50% is compression
            setZipProgress(50 + Math.round(metadata.percent / 2))
          }
        )

        const zipFile = new File([blob], `${folderName}.zip`, { type: 'application/zip' })
        setZipProgress(100)
        return zipFile
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to create archive'
        setError(message)
        return null
      } finally {
        setIsCreatingZip(false)
      }
    },
    [maxSize]
  )

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

  /**
   * Recursively read all files from a directory entry
   */
  const readDirectoryEntries = useCallback(
    async (entry: FileSystemDirectoryEntry): Promise<File[]> => {
      const files: File[] = []
      const reader = entry.createReader()

      // readEntries only returns batches, need to call repeatedly until empty
      const readBatch = (): Promise<FileSystemEntry[]> => {
        return new Promise((resolve, reject) => {
          reader.readEntries(resolve, reject)
        })
      }

      let batch: FileSystemEntry[]
      do {
        batch = await readBatch()
        for (const childEntry of batch) {
          if (childEntry.isFile) {
            const fileEntry = childEntry as FileSystemFileEntry
            const file = await new Promise<File>((resolve, reject) => {
              fileEntry.file(resolve, reject)
            })
            // Attach the path for zip creation
            Object.defineProperty(file, 'webkitRelativePath', {
              value: childEntry.fullPath.slice(1), // Remove leading /
              writable: false,
            })
            files.push(file)
          } else if (childEntry.isDirectory) {
            const subFiles = await readDirectoryEntries(childEntry as FileSystemDirectoryEntry)
            files.push(...subFiles)
          }
        }
      } while (batch.length > 0)

      return files
    },
    []
  )

  /**
   * Handle dropped items - detects folders and processes appropriately
   */
  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      if (disabled || isCreatingZip) return

      const items = e.dataTransfer.items
      if (!items || items.length === 0) {
        handleFiles(e.dataTransfer.files)
        return
      }

      // Check if any item is a directory
      const entries: FileSystemEntry[] = []
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.()
        if (entry) {
          entries.push(entry)
        }
      }

      // Check if we have a directory
      const hasDirectory = entries.some((entry) => entry.isDirectory)

      if (hasDirectory && uploadMode === 'folder') {
        // Find the first directory and process it
        const dirEntry = entries.find((entry) => entry.isDirectory) as FileSystemDirectoryEntry
        if (dirEntry) {
          try {
            setIsCreatingZip(true)
            setZipProgress(0)
            setError(null)

            // Read all files from the directory
            const files = await readDirectoryEntries(dirEntry)
            if (files.length === 0) {
              setError('Folder is empty or contains no files')
              setIsCreatingZip(false)
              return
            }

            // Create a pseudo FileList for createZipFromFolder
            // Use the directory name as the root
            const folderName = dirEntry.name
            for (const file of files) {
              // Prepend folder name to path
              const currentPath = (file as File & { webkitRelativePath: string }).webkitRelativePath
              Object.defineProperty(file, 'webkitRelativePath', {
                value: `${folderName}/${currentPath.split('/').slice(1).join('/')}`,
                writable: false,
                configurable: true,
              })
            }

            // Create the zip
            const zip = new JSZip()
            let totalSize = 0
            let processedSize = 0

            for (const file of files) {
              totalSize += file.size
            }

            if (totalSize > maxSize) {
              setError(`Folder size (${formatFileSize(totalSize)}) exceeds maximum (${formatFileSize(maxSize)})`)
              setIsCreatingZip(false)
              return
            }

            for (const file of files) {
              const fileWithPath = file as File & { webkitRelativePath: string }
              zip.file(fileWithPath.webkitRelativePath, file)
              processedSize += file.size
              setZipProgress(Math.round((processedSize / totalSize) * 50))
            }

            const blob = await zip.generateAsync(
              { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 1 } },
              (metadata) => {
                setZipProgress(50 + Math.round(metadata.percent / 2))
              }
            )

            const zipFile = new File([blob], `${folderName}.zip`, { type: 'application/zip' })
            setZipProgress(100)
            setIsCreatingZip(false)
            onFilesSelected([zipFile])
          } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to process folder'
            setError(message)
            setIsCreatingZip(false)
          }
          return
        }
      } else if (hasDirectory && uploadMode === 'files') {
        // User dropped a folder in files mode - show helpful error
        setError('Switch to "Folder" mode to upload folders, or drop individual files')
        setTimeout(() => setError(null), 5000)
        return
      }

      // No directories, handle as normal files
      handleFiles(e.dataTransfer.files)
    },
    [disabled, isCreatingZip, handleFiles, uploadMode, readDirectoryEntries, maxSize, onFilesSelected]
  )

  const handleClick = () => {
    if (disabled || isCreatingZip) return
    if (uploadMode === 'folder') {
      folderInputRef.current?.click()
    } else {
      inputRef.current?.click()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
    // Reset input so the same file can be selected again
    e.target.value = ''
  }

  const handleFolderInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    // Create zip from folder
    const zipFile = await createZipFromFolder(files)
    if (zipFile) {
      onFilesSelected([zipFile])
    }

    // Reset input
    e.target.value = ''
  }

  return (
    <div className="space-y-3">
      {/* Mode toggle */}
      {allowFolderUpload && (
        <div className="flex gap-2 justify-center">
          <button
            type="button"
            onClick={() => setUploadMode('files')}
            disabled={disabled || isCreatingZip}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              uploadMode === 'files'
                ? 'bg-accent-primary text-white'
                : 'bg-bg-tertiary text-text-muted hover:bg-bg-tertiary/80'
            } ${disabled || isCreatingZip ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <span className="flex items-center gap-2">
              <FileIcon className="w-4 h-4" />
              Files
            </span>
          </button>
          <button
            type="button"
            onClick={() => setUploadMode('folder')}
            disabled={disabled || isCreatingZip}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              uploadMode === 'folder'
                ? 'bg-accent-primary text-white'
                : 'bg-bg-tertiary text-text-muted hover:bg-bg-tertiary/80'
            } ${disabled || isCreatingZip ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <span className="flex items-center gap-2">
              <FolderIcon className="w-4 h-4" />
              Folder
            </span>
          </button>
        </div>
      )}

      {/* Drop zone */}
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${
            disabled || isCreatingZip
              ? 'border-bg-tertiary bg-bg-tertiary/50 cursor-not-allowed opacity-50'
              : isDragging
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-bg-tertiary hover:border-text-muted bg-bg-secondary'
          }
        `}
      >
        {/* File input for files mode */}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept.join(',')}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled || isCreatingZip}
        />

        {/* Folder input with webkitdirectory */}
        <input
          ref={folderInputRef}
          type="file"
          // @ts-expect-error - webkitdirectory is not in the standard types
          webkitdirectory=""
          directory=""
          onChange={handleFolderInputChange}
          className="hidden"
          disabled={disabled || isCreatingZip}
        />

        {isCreatingZip ? (
          /* Zip creation progress */
          <div className="flex flex-col items-center gap-3">
            <div className="w-16 h-16 rounded-full flex items-center justify-center bg-accent-primary/20">
              <svg className="w-8 h-8 text-accent-primary animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
            <div>
              <p className="text-text-primary font-medium">Creating archive...</p>
              <div className="mt-2 w-48 mx-auto bg-bg-tertiary rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-accent-primary transition-all duration-300"
                  style={{ width: `${zipProgress}%` }}
                />
              </div>
              <p className="text-sm text-text-muted mt-1">{zipProgress}%</p>
            </div>
          </div>
        ) : (
          /* Normal drop zone content */
          <div className="flex flex-col items-center gap-3">
            <div
              className={`w-16 h-16 rounded-full flex items-center justify-center ${
                isDragging ? 'bg-accent-primary/20 text-accent-primary' : 'bg-bg-tertiary text-text-muted'
              }`}
            >
              {uploadMode === 'folder' ? (
                <FolderIcon className="w-8 h-8" />
              ) : (
                <UploadIcon className="w-8 h-8" />
              )}
            </div>

            <div>
              <p className="text-text-primary font-medium">
                {isDragging
                  ? uploadMode === 'folder'
                    ? 'Drop folder here'
                    : 'Drop files here'
                  : uploadMode === 'folder'
                  ? 'Drag folder here or click to browse'
                  : 'Drag files here or click to browse'}
              </p>
              {uploadMode === 'files' && (
                <p className="text-sm text-text-muted mt-1">Supported: {accept.join(', ')}</p>
              )}
              {uploadMode === 'folder' && (
                <p className="text-sm text-text-muted mt-1">
                  Select a folder containing your design files
                </p>
              )}
              <p className="text-sm text-text-muted">Max size: {formatFileSize(maxSize)}</p>
            </div>
          </div>
        )}
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

function FileIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
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
