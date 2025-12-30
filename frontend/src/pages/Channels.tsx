import { useState } from 'react'
import { useChannels, useCreateChannel, useDeleteChannel } from '@/hooks/useChannels'
import { ChannelCard } from '@/components/channels/ChannelCard'
import { AddChannelModal } from '@/components/channels/AddChannelModal'
import { DeleteConfirmModal } from '@/components/channels/DeleteConfirmModal'
import { OPEN_TELEGRAM_AUTH_EVENT } from '@/components/layout/Layout'
import type { Channel, ChannelCreate } from '@/types/channel'

export function Channels() {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Channel | null>(null)

  const { data, isLoading, error } = useChannels()
  const createChannel = useCreateChannel()
  const deleteChannel = useDeleteChannel()

  const handleAddChannel = (formData: ChannelCreate) => {
    createChannel.mutate(formData, {
      onSuccess: () => {
        setIsAddModalOpen(false)
        createChannel.reset()
      },
    })
  }

  const handleDeleteClick = (id: string) => {
    const channel = data?.items.find((c) => c.id === id)
    if (channel) {
      setDeleteTarget(channel)
    }
  }

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return

    deleteChannel.mutate(deleteTarget.id, {
      onSuccess: () => {
        setDeleteTarget(null)
      },
    })
  }

  const handleAuthClick = () => {
    // Dispatch custom event to open auth modal in Layout
    window.dispatchEvent(new CustomEvent(OPEN_TELEGRAM_AUTH_EVENT))
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Channels</h1>
          {data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} channel{data.total !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors flex items-center gap-2"
        >
          <span>+</span>
          <span>Add Channel</span>
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="bg-bg-secondary rounded-lg p-8 flex justify-center">
          <div className="flex items-center gap-3 text-text-secondary">
            <svg
              className="animate-spin h-5 w-5"
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
            <span>Loading channels...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load channels: {error.message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">📡</div>
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No channels yet
          </h3>
          <p className="text-text-secondary mb-4">
            Add a Telegram channel to start monitoring for 3D designs.
          </p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors"
          >
            Add Your First Channel
          </button>
        </div>
      )}

      {/* Channel list */}
      {data && data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((channel) => (
            <ChannelCard
              key={channel.id}
              channel={channel}
              onDelete={handleDeleteClick}
              isDeleting={deleteChannel.isPending && deleteTarget?.id === channel.id}
            />
          ))}
        </div>
      )}

      {/* Add channel modal */}
      <AddChannelModal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false)
          createChannel.reset()
        }}
        onSubmit={handleAddChannel}
        isSubmitting={createChannel.isPending}
        error={
          createChannel.error
            ? (createChannel.error as Error).message ||
              'Failed to add channel'
            : null
        }
        onAuthClick={handleAuthClick}
      />

      {/* Delete confirmation modal */}
      <DeleteConfirmModal
        isOpen={!!deleteTarget}
        channelTitle={deleteTarget?.title || ''}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={deleteChannel.isPending}
      />
    </div>
  )
}
