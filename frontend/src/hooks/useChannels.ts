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
    mutationFn: (data: ChannelCreate) => channelsApi.create(data),
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
