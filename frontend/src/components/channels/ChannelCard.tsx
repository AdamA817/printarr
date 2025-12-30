import type { Channel } from '@/types/channel'

interface ChannelCardProps {
  channel: Channel
  onDelete: (id: string) => void
  isDeleting: boolean
}

export function ChannelCard({ channel, onDelete, isDeleting }: ChannelCardProps) {
  return (
    <div className="bg-bg-secondary rounded-lg p-4 flex items-center justify-between">
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

      <div className="flex items-center gap-4">
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${
            channel.is_enabled
              ? 'bg-accent-success/20 text-accent-success'
              : 'bg-text-muted/20 text-text-muted'
          }`}
        >
          {channel.is_enabled ? 'Enabled' : 'Disabled'}
        </span>

        <button
          onClick={() => onDelete(channel.id)}
          disabled={isDeleting}
          className="text-text-secondary hover:text-accent-danger transition-colors disabled:opacity-50"
          aria-label="Delete channel"
        >
          <svg
            className="w-5 h-5"
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
        </button>
      </div>
    </div>
  )
}
