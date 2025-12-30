import { useState, useEffect, useCallback } from 'react'
import { useTelegramStatus, useResolveChannel } from '@/hooks/useTelegramStatus'
import type { ChannelResolveResponse, TelegramErrorResponse } from '@/types/telegram'
import type { ChannelCreate } from '@/types/channel'
import { AxiosError } from 'axios'

interface AddChannelModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: ChannelCreate) => void
  isSubmitting: boolean
  error?: string | null
  onAuthClick?: () => void
}

export function AddChannelModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  error: submitError,
  onAuthClick,
}: AddChannelModalProps) {
  const [link, setLink] = useState('')
  const [title, setTitle] = useState('')
  const [resolvedChannel, setResolvedChannel] = useState<ChannelResolveResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { isAuthenticated } = useTelegramStatus()
  const resolveChannel = useResolveChannel()

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setLink('')
      setTitle('')
      setResolvedChannel(null)
      setError(null)
    }
  }, [isOpen])

  const handleResolve = useCallback(async () => {
    if (!link.trim()) return

    setError(null)
    setResolvedChannel(null)

    try {
      const result = await resolveChannel.mutateAsync({ link: link.trim() })
      setResolvedChannel(result)
      setTitle(result.title) // Pre-fill title from Telegram
    } catch (err) {
      if (err instanceof AxiosError && err.response?.data) {
        const errorData = err.response.data as TelegramErrorResponse
        setError(errorData.message || 'Failed to resolve channel')
      } else {
        setError('Failed to resolve channel')
      }
    }
  }, [link, resolveChannel])

  // Debounced auto-resolve when link changes
  useEffect(() => {
    if (!isAuthenticated || !link.trim()) return

    const timer = setTimeout(() => {
      // Check if it looks like a valid Telegram link or username
      const linkPattern = /^(@[\w]+|https?:\/\/t\.me\/[\w+]+|t\.me\/[\w+]+)$/i
      if (linkPattern.test(link.trim())) {
        handleResolve()
      }
    }, 800) // Debounce for 800ms

    return () => clearTimeout(timer)
  }, [link, isAuthenticated, handleResolve])

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!resolvedChannel || !title.trim()) return

    const channelData: ChannelCreate = {
      title: title.trim(),
      username: resolvedChannel.username || undefined,
      telegram_peer_id: resolvedChannel.id?.toString(),
      is_private: resolvedChannel.is_invite,
      invite_link: resolvedChannel.is_invite ? link.trim() : undefined,
    }

    onSubmit(channelData)
  }

  const handleClose = () => {
    onClose()
  }

  const combinedError = error || submitError

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <h2 className="text-lg font-semibold text-text-primary">
            Add Channel
          </h2>
          <button
            onClick={handleClose}
            className="text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Not authenticated warning */}
        {!isAuthenticated && (
          <div className="mx-4 mt-4 p-3 rounded-lg bg-accent-warning/20 border border-accent-warning/30">
            <div className="flex items-start gap-2">
              <WarningIcon className="w-5 h-5 text-accent-warning flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-accent-warning font-medium">
                  Not connected to Telegram
                </p>
                <p className="text-sm text-text-secondary mt-1">
                  You need to connect your Telegram account to add channels.
                </p>
                {onAuthClick && (
                  <button
                    onClick={onAuthClick}
                    className="mt-2 text-sm text-accent-primary hover:text-accent-primary/80"
                  >
                    Connect to Telegram
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {combinedError && (
            <div className="p-3 rounded-lg bg-accent-danger/20 border border-accent-danger/30">
              <p className="text-sm text-accent-danger">{combinedError}</p>
            </div>
          )}

          {/* Channel Link Input */}
          <div>
            <label
              htmlFor="link"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Channel Link or Username *
            </label>
            <div className="relative">
              <input
                id="link"
                type="text"
                value={link}
                onChange={(e) => {
                  setLink(e.target.value)
                  setResolvedChannel(null)
                }}
                placeholder="https://t.me/channel or @channel"
                className="w-full px-3 py-2 pr-10 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary disabled:opacity-50"
                disabled={!isAuthenticated}
                required
              />
              {resolveChannel.isPending && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <Spinner className="w-4 h-4 text-accent-primary" />
                </div>
              )}
              {resolvedChannel && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <CheckIcon className="w-5 h-5 text-accent-success" />
                </div>
              )}
            </div>
            <p className="mt-1 text-xs text-text-muted">
              Paste a t.me link, invite link, or @username
            </p>
          </div>

          {/* Resolved Channel Preview */}
          {resolvedChannel && (
            <div className="p-4 rounded-lg bg-bg-tertiary border border-bg-tertiary">
              <div className="flex items-start gap-3">
                {/* Channel Avatar */}
                <div className="w-12 h-12 rounded-full bg-accent-primary/20 flex items-center justify-center flex-shrink-0">
                  {resolvedChannel.photo_url ? (
                    <img
                      src={resolvedChannel.photo_url}
                      alt={resolvedChannel.title}
                      className="w-12 h-12 rounded-full object-cover"
                    />
                  ) : (
                    <ChannelIcon className="w-6 h-6 text-accent-primary" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-text-primary truncate">
                    {resolvedChannel.title}
                  </h3>
                  <div className="flex items-center gap-2 mt-1">
                    {resolvedChannel.username && (
                      <span className="text-sm text-text-secondary">
                        @{resolvedChannel.username}
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      resolvedChannel.is_invite
                        ? 'bg-accent-warning/20 text-accent-warning'
                        : 'bg-accent-success/20 text-accent-success'
                    }`}>
                      {resolvedChannel.is_invite ? 'Private' : 'Public'}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-bg-secondary text-text-muted capitalize">
                      {resolvedChannel.type}
                    </span>
                  </div>
                  {resolvedChannel.members_count && (
                    <p className="text-xs text-text-muted mt-1">
                      {resolvedChannel.members_count.toLocaleString()} members
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Title Input (editable) */}
          {resolvedChannel && (
            <div>
              <label
                htmlFor="title"
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                Display Name
              </label>
              <input
                id="title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Channel display name"
                className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary"
                required
              />
              <p className="mt-1 text-xs text-text-muted">
                You can customize the display name for this channel
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !resolvedChannel || !title.trim()}
              className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting && <Spinner className="w-4 h-4" />}
              {isSubmitting ? 'Adding...' : 'Add Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Icon Components

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

function CheckIcon({ className }: { className?: string }) {
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
        d="M5 13l4 4L19 7"
      />
    </svg>
  )
}

function WarningIcon({ className }: { className?: string }) {
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
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  )
}

function ChannelIcon({ className }: { className?: string }) {
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
        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
      />
    </svg>
  )
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
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
