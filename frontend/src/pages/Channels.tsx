import { useState } from 'react'
import { useChannels, useCreateChannel, useUpdateChannel, useDeleteChannel } from '@/hooks/useChannels'
import { useDiscoveredChannelStats } from '@/hooks/useDiscoveredChannels'
import { ChannelCard } from '@/components/channels/ChannelCard'
import { ChannelCardSkeleton } from '@/components/channels/ChannelCardSkeleton'
import { AddChannelModal } from '@/components/channels/AddChannelModal'
import { EditChannelModal } from '@/components/channels/EditChannelModal'
import { DeleteConfirmModal } from '@/components/channels/DeleteConfirmModal'
import { DiscoveredChannelsList } from '@/components/channels/DiscoveredChannelsList'
import { OPEN_TELEGRAM_AUTH_EVENT } from '@/components/layout/Layout'
import type { Channel, ChannelCreate, ChannelUpdate } from '@/types/channel'

type TabType = 'monitored' | 'discovered'

export function Channels() {
  const [activeTab, setActiveTab] = useState<TabType>('monitored')
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Channel | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Channel | null>(null)

  const { data, isLoading, error } = useChannels()
  const { data: discoveredStats } = useDiscoveredChannelStats()
  const createChannel = useCreateChannel()
  const updateChannel = useUpdateChannel()
  const deleteChannel = useDeleteChannel()

  const handleAddChannel = (formData: ChannelCreate) => {
    createChannel.mutate(formData, {
      onSuccess: () => {
        setIsAddModalOpen(false)
        createChannel.reset()
      },
    })
  }

  const handleEditChannel = (id: string, data: ChannelUpdate) => {
    updateChannel.mutate(
      { id, data },
      {
        onSuccess: () => {
          setEditTarget(null)
          updateChannel.reset()
        },
      }
    )
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

  const handleDiscoveredChannelAdded = () => {
    // Switch to monitored tab to show the newly added channel
    setActiveTab('monitored')
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Channels</h1>
          {activeTab === 'monitored' && data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} channel{data.total !== 1 ? 's' : ''} monitored
            </p>
          )}
        </div>
        {activeTab === 'monitored' && (
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors flex items-center gap-2"
          >
            <span>+</span>
            <span>Add Channel</span>
          </button>
        )}
      </div>

      {/* Tab navigation */}
      <div className="border-b border-bg-tertiary">
        <nav className="flex gap-4">
          <TabButton
            active={activeTab === 'monitored'}
            onClick={() => setActiveTab('monitored')}
            count={data?.total}
          >
            Monitored
          </TabButton>
          <TabButton
            active={activeTab === 'discovered'}
            onClick={() => setActiveTab('discovered')}
            count={discoveredStats?.total}
            highlight={discoveredStats?.new_this_week ? discoveredStats.new_this_week > 0 : false}
          >
            Discovered
          </TabButton>
        </nav>
      </div>

      {/* Monitored channels tab */}
      {activeTab === 'monitored' && (
        <>
          {/* Loading state */}
          {isLoading && (
            <div className="space-y-3">
              <ChannelCardSkeleton />
              <ChannelCardSkeleton />
              <ChannelCardSkeleton />
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
                  onEdit={setEditTarget}
                  onDelete={handleDeleteClick}
                  isDeleting={deleteChannel.isPending && deleteTarget?.id === channel.id}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Discovered channels tab */}
      {activeTab === 'discovered' && (
        <DiscoveredChannelsList onChannelAdded={handleDiscoveredChannelAdded} />
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

      {/* Edit channel modal */}
      <EditChannelModal
        isOpen={!!editTarget}
        channel={editTarget}
        onClose={() => {
          setEditTarget(null)
          updateChannel.reset()
        }}
        onSubmit={handleEditChannel}
        isSubmitting={updateChannel.isPending}
        error={
          updateChannel.error
            ? (updateChannel.error as Error).message || 'Failed to update channel'
            : null
        }
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

interface TabButtonProps {
  active: boolean
  onClick: () => void
  count?: number
  highlight?: boolean
  children: React.ReactNode
}

function TabButton({ active, onClick, count, highlight, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-accent-primary text-accent-primary'
          : 'border-transparent text-text-secondary hover:text-text-primary'
      }`}
    >
      <span>{children}</span>
      {typeof count === 'number' && (
        <span
          className={`ml-2 px-1.5 py-0.5 text-xs rounded ${
            highlight
              ? 'bg-accent-success text-white'
              : 'bg-bg-tertiary text-text-secondary'
          }`}
        >
          {count}
        </span>
      )}
    </button>
  )
}
