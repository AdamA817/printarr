import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { discoveredChannelsApi } from '@/services/api'
import type { DiscoveredChannelListParams, AddDiscoveredChannelRequest } from '@/types/discovered-channel'

export function useDiscoveredChannels(params?: DiscoveredChannelListParams) {
  return useQuery({
    queryKey: ['discoveredChannels', params],
    queryFn: () => discoveredChannelsApi.list(params),
  })
}

export function useDiscoveredChannel(id: string) {
  return useQuery({
    queryKey: ['discoveredChannel', id],
    queryFn: () => discoveredChannelsApi.get(id),
    enabled: !!id,
  })
}

export function useDiscoveredChannelStats() {
  return useQuery({
    queryKey: ['discoveredChannelStats'],
    queryFn: () => discoveredChannelsApi.stats(),
  })
}

export function useAddDiscoveredChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, request }: { id: string; request?: AddDiscoveredChannelRequest }) =>
      discoveredChannelsApi.add(id, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discoveredChannels'] })
      queryClient.invalidateQueries({ queryKey: ['discoveredChannelStats'] })
      queryClient.invalidateQueries({ queryKey: ['channels'] })
    },
  })
}

export function useDismissDiscoveredChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => discoveredChannelsApi.dismiss(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discoveredChannels'] })
      queryClient.invalidateQueries({ queryKey: ['discoveredChannelStats'] })
    },
  })
}
