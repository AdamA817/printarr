import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChannelCard } from '../ChannelCard'
import type { Channel } from '@/types/channel'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

const mockChannel: Channel = {
  id: '1',
  telegram_peer_id: '123456',
  title: 'Test Channel',
  username: 'testchannel',
  invite_link: null,
  is_private: false,
  is_enabled: true,
  backfill_mode: 'ALL_HISTORY',
  backfill_value: 0,
  download_mode: 'MANUAL',
  library_template_override: null,
  title_source_override: null,
  designer_source_override: null,
  last_ingested_message_id: null,
  last_backfill_checkpoint: null,
  last_sync_at: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

function renderChannelCard(
  channel: Channel = mockChannel,
  onEdit = vi.fn(),
  onDelete = vi.fn(),
  isDeleting = false
) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <ChannelCard channel={channel} onEdit={onEdit} onDelete={onDelete} isDeleting={isDeleting} />
    </QueryClientProvider>
  )
}

describe('ChannelCard', () => {
  it('renders channel title', () => {
    renderChannelCard()
    expect(screen.getByText('Test Channel')).toBeInTheDocument()
  })

  it('renders channel username with @ prefix', () => {
    renderChannelCard()
    expect(screen.getByText('@testchannel')).toBeInTheDocument()
  })

  it('shows enabled status badge', () => {
    renderChannelCard()
    expect(screen.getByText('Enabled')).toBeInTheDocument()
  })

  it('shows disabled status for disabled channel', () => {
    const disabledChannel = { ...mockChannel, is_enabled: false }
    renderChannelCard(disabledChannel)
    expect(screen.getByText('Disabled')).toBeInTheDocument()
  })

  it('shows lock icon for private channel', () => {
    const privateChannel = { ...mockChannel, is_private: true }
    renderChannelCard(privateChannel)
    // Private channels show lock emoji
    expect(screen.getByText('Test Channel').parentElement?.parentElement).toContainHTML('🔒')
  })

  it('calls onDelete when delete button clicked', () => {
    const onDelete = vi.fn()
    renderChannelCard(mockChannel, vi.fn(), onDelete)

    const deleteButton = screen.getByRole('button', { name: /delete/i })
    fireEvent.click(deleteButton)

    expect(onDelete).toHaveBeenCalledWith('1')
  })

  it('disables delete button when isDeleting is true', () => {
    renderChannelCard(mockChannel, vi.fn(), vi.fn(), true)

    const deleteButton = screen.getByRole('button', { name: /delete/i })
    expect(deleteButton).toBeDisabled()
  })

  it('shows expand button when channel has telegram_peer_id', () => {
    renderChannelCard()
    // Should have chevron button for expanding messages
    const expandButton = screen.getByRole('button', { name: /expand|collapse/i })
    expect(expandButton).toBeInTheDocument()
  })

  it('does not show expand button when channel has no telegram_peer_id', () => {
    const channelWithoutTelegramId = { ...mockChannel, telegram_peer_id: '' }
    renderChannelCard(channelWithoutTelegramId)

    const buttons = screen.getAllByRole('button')
    // Should have edit and delete buttons, but not expand
    expect(buttons).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /expand|collapse/i })).not.toBeInTheDocument()
  })

  it('calls onEdit when edit button clicked', () => {
    const onEdit = vi.fn()
    renderChannelCard(mockChannel, onEdit)

    const editButton = screen.getByRole('button', { name: /edit/i })
    fireEvent.click(editButton)

    expect(onEdit).toHaveBeenCalledWith(mockChannel)
  })
})
