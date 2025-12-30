import { useTelegramStatus, useChannelMessages } from '@/hooks/useTelegramStatus'
import type { Message, MessageAttachment } from '@/types/telegram'

interface MessagesPanelProps {
  channelId: number | null
  channelTitle?: string
}

export function MessagesPanel({ channelId, channelTitle }: MessagesPanelProps) {
  const { isAuthenticated } = useTelegramStatus()
  const { data, isLoading, error, refetch, isFetching } = useChannelMessages(channelId)

  // Not authenticated state
  if (!isAuthenticated) {
    return (
      <div className="bg-bg-secondary rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <MessagesIcon className="w-5 h-5 text-text-secondary" />
          <h3 className="font-medium text-text-primary">Recent Messages</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="w-12 h-12 rounded-full bg-accent-warning/20 flex items-center justify-center mb-3">
            <WarningIcon className="w-6 h-6 text-accent-warning" />
          </div>
          <p className="text-text-secondary text-sm">
            Connect to Telegram to view messages
          </p>
        </div>
      </div>
    )
  }

  // No channel ID
  if (!channelId) {
    return (
      <div className="bg-bg-secondary rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <MessagesIcon className="w-5 h-5 text-text-secondary" />
          <h3 className="font-medium text-text-primary">Recent Messages</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <p className="text-text-muted text-sm">
            No Telegram channel linked
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-bg-secondary rounded-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
        <div className="flex items-center gap-3">
          <MessagesIcon className="w-5 h-5 text-text-secondary" />
          <h3 className="font-medium text-text-primary">Recent Messages</h3>
          {channelTitle && (
            <span className="text-sm text-text-muted">from {channelTitle}</span>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50"
          aria-label="Refresh messages"
        >
          <RefreshIcon className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Loading state */}
        {isLoading && (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <MessageSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="p-4 rounded-lg bg-accent-danger/20 border border-accent-danger/30">
            <p className="text-sm text-accent-danger">
              Failed to load messages: {(error as Error).message}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-2 text-sm text-accent-primary hover:text-accent-primary/80"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty state */}
        {data && data.messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-bg-tertiary flex items-center justify-center mb-3">
              <MessagesIcon className="w-6 h-6 text-text-muted" />
            </div>
            <p className="text-text-muted text-sm">
              No messages found
            </p>
          </div>
        )}

        {/* Messages list */}
        {data && data.messages.length > 0 && (
          <div className="space-y-3">
            {data.messages.map((message) => (
              <MessageCard key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function MessageCard({ message }: { message: Message }) {
  const formattedDate = message.date ? formatRelativeTime(message.date) : null

  return (
    <div className="p-3 rounded-lg bg-bg-tertiary border border-bg-tertiary hover:border-text-muted/20 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {/* Avatar */}
          <div className="w-8 h-8 rounded-full bg-accent-primary/20 flex items-center justify-center text-sm font-medium text-accent-primary">
            {message.sender?.name?.charAt(0).toUpperCase() || '?'}
          </div>
          <div>
            <span className="text-sm font-medium text-text-primary">
              {message.sender?.name || 'Unknown'}
            </span>
            {message.sender?.username && (
              <span className="text-xs text-text-muted ml-1">
                @{message.sender.username}
              </span>
            )}
          </div>
        </div>
        {formattedDate && (
          <span className="text-xs text-text-muted">{formattedDate}</span>
        )}
      </div>

      {/* Forward indicator */}
      {message.forward_from && (
        <div className="flex items-center gap-1 mb-2 text-xs text-text-muted">
          <ForwardIcon className="w-3 h-3" />
          <span>Forwarded from {message.forward_from}</span>
        </div>
      )}

      {/* Text content */}
      {message.text && (
        <p className="text-sm text-text-secondary whitespace-pre-wrap break-words">
          {message.text}
        </p>
      )}

      {/* Attachments */}
      {message.attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {message.attachments.map((attachment, index) => (
            <AttachmentBadge key={index} attachment={attachment} />
          ))}
        </div>
      )}
    </div>
  )
}

function AttachmentBadge({ attachment }: { attachment: MessageAttachment }) {
  const icon = getAttachmentIcon(attachment.type)
  const sizeStr = attachment.size ? formatFileSize(attachment.size) : null

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-secondary text-xs">
      <span>{icon}</span>
      {attachment.filename ? (
        <span className="text-text-secondary truncate max-w-[150px]">
          {attachment.filename}
        </span>
      ) : (
        <span className="text-text-muted capitalize">{attachment.type}</span>
      )}
      {sizeStr && (
        <span className="text-text-muted">({sizeStr})</span>
      )}
    </div>
  )
}

function MessageSkeleton() {
  return (
    <div className="p-3 rounded-lg bg-bg-tertiary animate-pulse">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-bg-secondary" />
        <div className="h-4 w-24 bg-bg-secondary rounded" />
        <div className="h-3 w-16 bg-bg-secondary rounded ml-auto" />
      </div>
      <div className="space-y-2">
        <div className="h-3 w-full bg-bg-secondary rounded" />
        <div className="h-3 w-3/4 bg-bg-secondary rounded" />
      </div>
    </div>
  )
}

// Utility functions

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getAttachmentIcon(type: string): string {
  switch (type) {
    case 'photo':
      return '📷'
    case 'document':
      return '📎'
    case 'video':
      return '🎥'
    case 'audio':
      return '🎵'
    default:
      return '📁'
  }
}

// Icon Components

function MessagesIcon({ className }: { className?: string }) {
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
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
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
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
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

function ForwardIcon({ className }: { className?: string }) {
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
        d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
      />
    </svg>
  )
}
