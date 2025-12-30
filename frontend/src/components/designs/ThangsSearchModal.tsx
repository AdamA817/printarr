import { useState, useEffect, useCallback, useRef } from 'react'
import { useThangsSearch } from '@/hooks/useThangs'
import { useLinkToThangs } from '@/hooks/useDesigns'
import type { ThangsSearchResult } from '@/types/design'

interface ThangsSearchModalProps {
  isOpen: boolean
  onClose: () => void
  designId: string
  designTitle: string
}

// Main wrapper that conditionally renders the content
export function ThangsSearchModal({
  isOpen,
  onClose,
  designId,
  designTitle,
}: ThangsSearchModalProps) {
  if (!isOpen) return null

  // Using key to reset state when modal reopens
  return (
    <ThangsSearchModalContent
      key={designId}
      onClose={onClose}
      designId={designId}
      designTitle={designTitle}
    />
  )
}

// Internal component with all the state - resets when unmounted
function ThangsSearchModalContent({
  onClose,
  designId,
  designTitle,
}: Omit<ThangsSearchModalProps, 'isOpen'>) {
  const [searchQuery, setSearchQuery] = useState(designTitle)
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'search' | 'url'>('search')
  const [linkUrl, setLinkUrl] = useState('')
  const [linkError, setLinkError] = useState<string | null>(null)
  const [linkingModelId, setLinkingModelId] = useState<string | null>(null)

  const inputRef = useRef<HTMLInputElement>(null)

  const { data: searchData, isLoading, error } = useThangsSearch(
    submittedQuery ? { q: submittedQuery, limit: 20 } : null
  )

  const linkMutation = useLinkToThangs()

  // Focus input when modal mounts
  useEffect(() => {
    const timer = setTimeout(() => inputRef.current?.focus(), 100)
    return () => clearTimeout(timer)
  }, [])

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleSearch = useCallback(() => {
    if (searchQuery.trim().length >= 3) {
      setSubmittedQuery(searchQuery.trim())
    }
  }, [searchQuery])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const handleLinkResult = async (result: ThangsSearchResult) => {
    setLinkingModelId(result.model_id)
    setLinkError(null)

    try {
      await linkMutation.mutateAsync({
        id: designId,
        data: {
          model_id: result.model_id,
          url: result.url,
        },
      })
      onClose()
    } catch (err) {
      setLinkError((err as Error).message || 'Failed to link to Thangs')
      setLinkingModelId(null)
    }
  }

  const handleLinkByUrl = async () => {
    if (!linkUrl.trim()) return
    setLinkError(null)

    // Extract model_id from URL
    const urlMatch = linkUrl.match(/thangs\.com\/.*?\/([a-zA-Z0-9-]+)(?:\?|$|#)/)
    if (!urlMatch) {
      setLinkError('Invalid Thangs URL. Please enter a valid thangs.com model URL.')
      return
    }

    const modelId = urlMatch[1]
    setLinkingModelId(modelId)

    try {
      await linkMutation.mutateAsync({
        id: designId,
        data: {
          model_id: modelId,
          url: linkUrl.trim(),
        },
      })
      onClose()
    } catch (err) {
      setLinkError((err as Error).message || 'Failed to link to Thangs')
      setLinkingModelId(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-end sm:items-center justify-center p-0 sm:p-4">
        <div className="relative w-full sm:max-w-2xl bg-bg-primary rounded-t-lg sm:rounded-lg shadow-xl transform transition-all max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-bg-tertiary">
            <div>
              <h2 className="text-lg font-medium text-text-primary">
                Link to Thangs
              </h2>
              <p className="text-sm text-text-muted mt-0.5">
                Search for "{designTitle}"
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
              aria-label="Close"
            >
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-bg-tertiary px-6">
            <button
              onClick={() => setActiveTab('search')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'search'
                  ? 'border-accent-primary text-accent-primary'
                  : 'border-transparent text-text-muted hover:text-text-secondary'
              }`}
            >
              Search
            </button>
            <button
              onClick={() => setActiveTab('url')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'url'
                  ? 'border-accent-primary text-accent-primary'
                  : 'border-transparent text-text-muted hover:text-text-secondary'
              }`}
            >
              Link by URL
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'search' ? (
              <div className="space-y-4">
                {/* Search Input */}
                <div className="flex gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Search Thangs..."
                    className="flex-1 px-4 py-2 bg-bg-secondary rounded text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={searchQuery.trim().length < 3 || isLoading}
                    className="px-4 py-2 bg-accent-primary text-white rounded hover:bg-accent-primary/80 transition-colors disabled:opacity-50"
                  >
                    {isLoading ? 'Searching...' : 'Search'}
                  </button>
                </div>

                {searchQuery.trim().length > 0 && searchQuery.trim().length < 3 && (
                  <p className="text-xs text-text-muted">
                    Enter at least 3 characters to search
                  </p>
                )}

                {/* Error State */}
                {error && (
                  <div className="p-4 bg-accent-danger/20 rounded-lg">
                    <p className="text-sm text-accent-danger">
                      {(error as Error).message || 'Failed to search Thangs. Please try again.'}
                    </p>
                  </div>
                )}

                {/* Loading State */}
                {isLoading && (
                  <div className="py-8 text-center">
                    <LoadingSpinner />
                    <p className="text-sm text-text-muted mt-2">Searching Thangs...</p>
                  </div>
                )}

                {/* Results */}
                {!isLoading && searchData && (
                  <div className="space-y-2">
                    {searchData.results.length === 0 ? (
                      <div className="py-8 text-center">
                        <p className="text-text-muted">No results found</p>
                        <p className="text-sm text-text-muted mt-1">
                          Try a different search term
                        </p>
                      </div>
                    ) : (
                      <>
                        <p className="text-xs text-text-muted">
                          {searchData.total} result{searchData.total !== 1 ? 's' : ''} found
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {searchData.results.map((result) => (
                            <SearchResultCard
                              key={result.model_id}
                              result={result}
                              onLink={() => handleLinkResult(result)}
                              isLinking={linkingModelId === result.model_id}
                            />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-text-secondary">
                  Paste a Thangs model URL to link directly.
                </p>
                <input
                  type="url"
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://thangs.com/designer/username/model-name"
                  className="w-full px-4 py-2 bg-bg-secondary rounded text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
                />
                <button
                  onClick={handleLinkByUrl}
                  disabled={!linkUrl.trim() || linkingModelId !== null}
                  className="w-full px-4 py-2 bg-accent-primary text-white rounded hover:bg-accent-primary/80 transition-colors disabled:opacity-50"
                >
                  {linkingModelId ? 'Linking...' : 'Link'}
                </button>
              </div>
            )}

            {/* Link Error */}
            {linkError && (
              <div className="mt-4 p-3 bg-accent-danger/20 rounded-lg">
                <p className="text-sm text-accent-danger">{linkError}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface SearchResultCardProps {
  result: ThangsSearchResult
  onLink: () => void
  isLinking: boolean
}

function SearchResultCard({ result, onLink, isLinking }: SearchResultCardProps) {
  return (
    <div className="bg-bg-secondary rounded-lg p-3 flex gap-3">
      {/* Thumbnail */}
      <div className="w-16 h-16 flex-shrink-0 rounded bg-bg-tertiary overflow-hidden">
        {result.thumbnail_url ? (
          <img
            src={result.thumbnail_url}
            alt={result.title}
            className="w-full h-full object-cover"
            onError={(e) => {
              // Hide image on error
              (e.target as HTMLImageElement).style.display = 'none'
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-text-muted">
            <ModelIcon className="w-8 h-8" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-text-primary truncate" title={result.title}>
          {result.title}
        </h4>
        {result.designer && (
          <p className="text-xs text-text-muted truncate">
            by {result.designer}
          </p>
        )}
        <div className="mt-2 flex gap-2">
          <button
            onClick={onLink}
            disabled={isLinking}
            className="text-xs px-2 py-1 bg-accent-primary text-white rounded hover:bg-accent-primary/80 transition-colors disabled:opacity-50"
          >
            {isLinking ? 'Linking...' : 'Link'}
          </button>
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs px-2 py-1 bg-bg-tertiary text-text-secondary rounded hover:text-text-primary transition-colors"
          >
            View
          </a>
        </div>
      </div>
    </div>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
}

function ModelIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"
      />
    </svg>
  )
}

function LoadingSpinner() {
  return (
    <svg
      className="animate-spin h-8 w-8 text-accent-primary mx-auto"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
