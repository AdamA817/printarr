import { useState } from 'react'
import type { DiscoveredChannel, DiscoveredChannelListParams } from '@/types/discovered-channel'
import {
  useDiscoveredChannels,
  useDiscoveredChannelStats,
  useDismissDiscoveredChannel,
} from '@/hooks/useDiscoveredChannels'
import { AddDiscoveredChannelModal } from './AddDiscoveredChannelModal'

interface DiscoveredChannelsListProps {
  onChannelAdded?: (channelId: string, title: string) => void
}

export function DiscoveredChannelsList({ onChannelAdded }: DiscoveredChannelsListProps) {
  const [params, setParams] = useState<DiscoveredChannelListParams>({
    page: 1,
    page_size: 20,
    sort_by: 'reference_count',
    sort_order: 'desc',
    exclude_added: true,
  })
  const [addTarget, setAddTarget] = useState<DiscoveredChannel | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const { data, isLoading, error } = useDiscoveredChannels(params)
  const { data: stats } = useDiscoveredChannelStats()
  const dismissChannel = useDismissDiscoveredChannel()

  const handleDismiss = async (channel: DiscoveredChannel) => {
    try {
      await dismissChannel.mutateAsync(channel.id)
    } catch (error) {
      console.error('Failed to dismiss channel:', error)
    }
  }

  const handleAddSuccess = (channelId: string, title: string) => {
    setSuccessMessage(`Added "${title}" to monitored channels`)
    onChannelAdded?.(channelId, title)
    // Clear success message after 5 seconds
    setTimeout(() => setSuccessMessage(null), 5000)
  }

  const handleSortChange = (sortBy: 'reference_count' | 'last_seen_at' | 'first_seen_at') => {
    setParams((prev) => ({
      ...prev,
      sort_by: sortBy,
      page: 1,
    }))
  }

  return (
    <div className="space-y-4">
      {/* Stats header */}
      {stats && (
        <div className="flex items-center gap-4 text-sm text-text-secondary">
          <span>
            <strong className="text-text-primary">{stats.total}</strong> channels discovered
          </span>
          {stats.new_this_week > 0 && (
            <span className="text-accent-success">
              +{stats.new_this_week} new this week
            </span>
          )}
        </div>
      )}

      {/* Success message */}
      {successMessage && (
        <div className="p-3 rounded-lg bg-accent-success/20 border border-accent-success/30">
          <p className="text-sm text-accent-success">{successMessage}</p>
        </div>
      )}

      {/* Sort controls */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-text-secondary">Sort by:</span>
        <div className="flex gap-1">
          {[
            { value: 'reference_count', label: 'References' },
            { value: 'last_seen_at', label: 'Last Seen' },
            { value: 'first_seen_at', label: 'First Seen' },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => handleSortChange(option.value as 'reference_count' | 'last_seen_at' | 'first_seen_at')}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                params.sort_by === option.value
                  ? 'bg-accent-primary text-white'
                  : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-bg-secondary rounded-lg p-4 animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-bg-tertiary" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-bg-tertiary rounded w-1/3" />
                  <div className="h-3 bg-bg-tertiary rounded w-1/4" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load discovered channels: {error.message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">🔍</div>
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No channels discovered yet
          </h3>
          <p className="text-text-secondary">
            Channels referenced in your monitored content will appear here.
          </p>
        </div>
      )}

      {/* Channel list */}
      {data && data.items.length > 0 && (
        <div className="space-y-2">
          {data.items.map((channel) => (
            <DiscoveredChannelRow
              key={channel.id}
              channel={channel}
              onAdd={() => setAddTarget(channel)}
              onDismiss={() => handleDismiss(channel)}
              isDismissing={dismissChannel.isPending}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setParams((prev) => ({ ...prev, page: (prev.page || 1) - 1 }))}
            disabled={params.page === 1}
            className="px-3 py-1 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-text-secondary">
            Page {params.page} of {data.pages}
          </span>
          <button
            onClick={() => setParams((prev) => ({ ...prev, page: (prev.page || 1) + 1 }))}
            disabled={params.page === data.pages}
            className="px-3 py-1 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}

      {/* Add channel modal */}
      <AddDiscoveredChannelModal
        isOpen={!!addTarget}
        channel={addTarget}
        onClose={() => setAddTarget(null)}
        onSuccess={handleAddSuccess}
      />
    </div>
  )
}

interface DiscoveredChannelRowProps {
  channel: DiscoveredChannel
  onAdd: () => void
  onDismiss: () => void
  isDismissing: boolean
}

function DiscoveredChannelRow({
  channel,
  onAdd,
  onDismiss,
  isDismissing,
}: DiscoveredChannelRowProps) {
  const displayTitle = channel.title || channel.username || 'Unknown Channel'
  const lastSeen = new Date(channel.last_seen_at).toLocaleDateString()

  return (
    <div className="bg-bg-secondary rounded-lg p-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary">
          {channel.is_private ? '🔒' : '📡'}
        </div>
        <div>
          <h3 className="font-medium text-text-primary">{displayTitle}</h3>
          <div className="flex items-center gap-3 text-sm text-text-secondary">
            {channel.username && <span>@{channel.username}</span>}
            <span>{channel.reference_count} reference{channel.reference_count !== 1 ? 's' : ''}</span>
            <span>Last seen: {lastSeen}</span>
          </div>
          {/* Source type badges */}
          {channel.source_types.length > 0 && (
            <div className="flex gap-1 mt-1">
              {channel.source_types.map((type) => (
                <span
                  key={type}
                  className="px-1.5 py-0.5 text-xs rounded bg-bg-tertiary text-text-secondary"
                >
                  {type}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onAdd}
          className="px-3 py-1.5 text-sm bg-accent-primary text-white rounded hover:bg-accent-primary/80 transition-colors"
        >
          Add Channel
        </button>
        <button
          onClick={onDismiss}
          disabled={isDismissing}
          className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors disabled:opacity-50"
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
