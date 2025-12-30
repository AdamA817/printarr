import { useState } from 'react'
import type { Channel } from '@/types/channel'
import { MessagesPanel } from './MessagesPanel'

interface ChannelCardProps {
  channel: Channel
  onEdit: (channel: Channel) => void
  onDelete: (id: string) => void
  isDeleting: boolean
}

export function ChannelCard({ channel, onEdit, onDelete, isDeleting }: ChannelCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Parse telegram_peer_id to number if present
  const telegramId = channel.telegram_peer_id
    ? parseInt(channel.telegram_peer_id, 10)
    : null

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      {/* Main card content */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary">
            {channel.is_private ? '🔒' : '📡'}
          </div>
          <div>
            <h3 className="font-medium text-text-primary">{channel.title}</h3>
            <p className="text-sm text-text-secondary">
              {channel.username ? `@${channel.username}` : 'No username'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${
              channel.is_enabled
                ? 'bg-accent-success/20 text-accent-success'
                : 'bg-text-muted/20 text-text-muted'
            }`}
          >
            {channel.is_enabled ? 'Enabled' : 'Disabled'}
          </span>

          {/* Expand/Collapse button */}
          {telegramId && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
              aria-label={isExpanded ? 'Collapse messages' : 'Expand messages'}
              title={isExpanded ? 'Hide messages' : 'Show messages'}
            >
              <ChevronIcon className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
            </button>
          )}

          <button
            onClick={() => onEdit(channel)}
            className="p-2 text-text-secondary hover:text-accent-primary hover:bg-bg-tertiary rounded transition-colors"
            aria-label="Edit channel"
            title="Edit channel"
          >
            <EditIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => onDelete(channel.id)}
            disabled={isDeleting}
            className="p-2 text-text-secondary hover:text-accent-danger hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50"
            aria-label="Delete channel"
            title="Delete channel"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Messages panel (expandable) */}
      {isExpanded && telegramId && (
        <div className="border-t border-bg-tertiary">
          <MessagesPanel channelId={telegramId} channelTitle={channel.title} />
        </div>
      )}
    </div>
  )
}

function ChevronIcon({ className }: { className?: string }) {
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
        d="M19 9l-7 7-7-7"
      />
    </svg>
  )
}

function EditIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
      />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
