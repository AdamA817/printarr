import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queueApi, activityApi } from '@/services/api'
import type { QueueListParams, ActivityListParams } from '@/types/queue'

// Queue hooks
export function useQueue(params?: QueueListParams) {
  return useQuery({
    queryKey: ['queue', params],
    queryFn: () => queueApi.list(params),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  })
}

export function useQueueStats() {
  return useQuery({
    queryKey: ['queueStats'],
    queryFn: () => queueApi.stats(),
    refetchInterval: 5000,
  })
}

export function useUpdateJobPriority() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ jobId, priority }: { jobId: string; priority: number }) =>
      queueApi.updatePriority(jobId, priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useCancelJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId: string) => queueApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      queryClient.invalidateQueries({ queryKey: ['queueStats'] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

// Activity hooks
export function useActivity(params?: ActivityListParams) {
  return useQuery({
    queryKey: ['activity', params],
    queryFn: () => activityApi.list(params),
  })
}

export function useRemoveActivity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId: string) => activityApi.remove(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}
