import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { channelsApi, type ChannelListParams } from '@/services/api'
import type { Channel, ChannelCreate, ChannelUpdate, ChannelList, DownloadMode, DownloadModeRequest } from '@/types/channel'

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
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['channels'] })
      await queryClient.cancelQueries({ queryKey: ['channel', id] })

      // Snapshot previous values
      const previousChannels = queryClient.getQueriesData<ChannelList>({ queryKey: ['channels'] })
      const previousChannel = queryClient.getQueryData<Channel>(['channel', id])

      // Optimistically update channel in list
      queryClient.setQueriesData<ChannelList>({ queryKey: ['channels'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((channel) =>
            channel.id === id ? { ...channel, ...data } : channel
          ),
        }
      })

      // Optimistically update single channel query
      if (previousChannel) {
        queryClient.setQueryData<Channel>(['channel', id], {
          ...previousChannel,
          ...data,
        })
      }

      return { previousChannels, previousChannel }
    },
    onError: (_err, { id }, context) => {
      // Rollback on error
      if (context?.previousChannels) {
        for (const [queryKey, data] of context.previousChannels) {
          queryClient.setQueryData(queryKey, data)
        }
      }
      if (context?.previousChannel) {
        queryClient.setQueryData(['channel', id], context.previousChannel)
      }
    },
    onSettled: (_, __, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      queryClient.invalidateQueries({ queryKey: ['channel', id] })
    },
  })
}

export function useDeleteChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => channelsApi.delete(id),
    onMutate: async (id) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['channels'] })

      // Snapshot previous value
      const previousChannels = queryClient.getQueriesData<ChannelList>({ queryKey: ['channels'] })

      // Optimistically remove from list
      queryClient.setQueriesData<ChannelList>({ queryKey: ['channels'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.filter((channel) => channel.id !== id),
          total: old.total - 1,
        }
      })

      return { previousChannels }
    },
    onError: (_err, _id, context) => {
      // Rollback on error
      if (context?.previousChannels) {
        for (const [queryKey, data] of context.previousChannels) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })
}

export function useTriggerBackfill() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (channelId: string) => channelsApi.triggerBackfill(channelId),
    onSuccess: () => {
      // Invalidate designs and stats since backfill may have created new designs
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

// Download mode hooks (v0.6)
export function useDownloadModePreview(channelId: string, newMode: DownloadMode | null) {
  return useQuery({
    queryKey: ['downloadModePreview', channelId, newMode],
    queryFn: () => channelsApi.previewDownloadMode(channelId, newMode!),
    enabled: !!channelId && newMode === 'DOWNLOAD_ALL',
  })
}

export function useUpdateDownloadMode() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ channelId, request }: { channelId: string; request: DownloadModeRequest }) =>
      channelsApi.updateDownloadMode(channelId, request),
    onMutate: async ({ channelId, request }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['channels'] })
      await queryClient.cancelQueries({ queryKey: ['channel', channelId] })

      // Snapshot previous values
      const previousChannels = queryClient.getQueriesData<ChannelList>({ queryKey: ['channels'] })
      const previousChannel = queryClient.getQueryData<Channel>(['channel', channelId])

      // Optimistically update download_mode in channel list
      queryClient.setQueriesData<ChannelList>({ queryKey: ['channels'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((channel) =>
            channel.id === channelId
              ? { ...channel, download_mode: request.download_mode }
              : channel
          ),
        }
      })

      // Optimistically update single channel query
      if (previousChannel) {
        queryClient.setQueryData<Channel>(['channel', channelId], {
          ...previousChannel,
          download_mode: request.download_mode,
        })
      }

      return { previousChannels, previousChannel }
    },
    onError: (_err, { channelId }, context) => {
      // Rollback on error
      if (context?.previousChannels) {
        for (const [queryKey, data] of context.previousChannels) {
          queryClient.setQueryData(queryKey, data)
        }
      }
      if (context?.previousChannel) {
        queryClient.setQueryData(['channel', channelId], context.previousChannel)
      }
    },
    onSettled: (_, __, { channelId }) => {
      queryClient.invalidateQueries({ queryKey: ['channels'] })
      queryClient.invalidateQueries({ queryKey: ['channel', channelId] })
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}
