import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { channelsApi, type ChannelListParams } from '@/services/api'
import type { ChannelCreate, ChannelUpdate } from '@/types/channel'

export function useChannels(params?: ChannelListParams) {
  return useQuery({
    queryKey: ['channels', params],
    queryFn: () => channelsApi.list(params),
  })
}

export function useChannel(id: string) {
  return useQuery({
    queryKey: ['channel', id],
    queryFn: () => channelsApi.get(id),
    enabled: !!id,
  })
}

export function useCreateChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: ChannelCreate) => {
      // Extract backfill settings (not sent to create endpoint)
      const { backfill_mode, backfill_value, start_backfill, ...createData } = data

      // Step 1: Create the channel
      const channel = await channelsApi.create(createData)

      // Step 2: Update backfill settings if they differ from defaults
      const needsUpdate = backfill_mode && (
        backfill_mode !== 'LAST_N_MESSAGES' ||
        backfill_value !== 100
      )

      if (needsUpdate) {
        await channelsApi.update(channel.id, {
          backfill_mode,
          backfill_value,
        })
      }

      // Step 3: Trigger backfill if requested
      if (start_backfill && backfill_mode) {
        // Fire and forget - don't wait for backfill to complete
        channelsApi.triggerBackfill(channel.id).catch((err) => {
          console.error('Failed to trigger backfill:', err)
        })
      }

      return channel
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })
}

export function useUpdateChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ChannelUpdate }) =>
      channelsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })
}

export function useDeleteChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => channelsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })
}
