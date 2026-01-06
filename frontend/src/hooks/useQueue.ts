import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queueApi, activityApi } from '@/services/api'
import { useSSEStatus } from '@/contexts/SSEContext'
import type { QueueListParams, ActivityListParams, QueueList, ActivityList } from '@/types/queue'

// Queue hooks
export function useQueue(params?: QueueListParams) {
  const sseStatus = useSSEStatus()
  const isSSEConnected = sseStatus === 'connected'

  return useQuery({
    queryKey: ['queue', params],
    queryFn: () => queueApi.list(params),
    // Only poll as fallback when SSE is disconnected - SSE handles real-time updates
    refetchInterval: isSSEConnected ? false : 10000,
  })
}

export function useQueueStats() {
  const sseStatus = useSSEStatus()
  const isSSEConnected = sseStatus === 'connected'

  return useQuery({
    queryKey: ['queueStats'],
    queryFn: () => queueApi.stats(),
    // Only poll as fallback when SSE is disconnected - SSE handles real-time updates
    refetchInterval: isSSEConnected ? false : 10000,
  })
}

export function useUpdateJobPriority() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ jobId, priority }: { jobId: string; priority: number }) =>
      queueApi.updatePriority(jobId, priority),
    onMutate: async ({ jobId, priority }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['queue'] })

      // Snapshot previous value
      const previousQueue = queryClient.getQueriesData<QueueList>({ queryKey: ['queue'] })

      // Optimistically update priority in all queue queries
      queryClient.setQueriesData<QueueList>({ queryKey: ['queue'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((item) =>
            item.id === jobId ? { ...item, priority } : item
          ),
        }
      })

      return { previousQueue }
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousQueue) {
        for (const [queryKey, data] of context.previousQueue) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
    },
  })
}

export function useCancelJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId: string) => queueApi.cancel(jobId),
    onMutate: async (jobId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['queue'] })

      // Snapshot previous value
      const previousQueue = queryClient.getQueriesData<QueueList>({ queryKey: ['queue'] })

      // Optimistically remove job from queue
      queryClient.setQueriesData<QueueList>({ queryKey: ['queue'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.filter((item) => item.id !== jobId),
          total: old.total - 1,
        }
      })

      return { previousQueue }
    },
    onError: (_err, _jobId, context) => {
      // Rollback on error
      if (context?.previousQueue) {
        for (const [queryKey, data] of context.previousQueue) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      queryClient.invalidateQueries({ queryKey: ['queueStats'] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

// DEC-042: Retry a failed/canceled job
export function useRetryJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId: string) => queueApi.retry(jobId),
    onMutate: async (jobId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['activity'] })

      // Snapshot previous value
      const previousActivity = queryClient.getQueriesData<ActivityList>({ queryKey: ['activity'] })

      // Optimistically update the job status in activity to show it's being retried
      queryClient.setQueriesData<ActivityList>({ queryKey: ['activity'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((item) =>
            item.id === jobId ? { ...item, status: 'QUEUED' as const } : item
          ),
        }
      })

      return { previousActivity }
    },
    onError: (_err, _jobId, context) => {
      // Rollback on error
      if (context?.previousActivity) {
        for (const [queryKey, data] of context.previousActivity) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      queryClient.invalidateQueries({ queryKey: ['queueStats'] })
      queryClient.invalidateQueries({ queryKey: ['activity'] })
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
    onMutate: async (jobId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['activity'] })

      // Snapshot previous value
      const previousActivity = queryClient.getQueriesData<ActivityList>({ queryKey: ['activity'] })

      // Optimistically remove from activity list
      queryClient.setQueriesData<ActivityList>({ queryKey: ['activity'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.filter((item) => item.id !== jobId),
          total: old.total - 1,
        }
      })

      return { previousActivity }
    },
    onError: (_err, _jobId, context) => {
      // Rollback on error
      if (context?.previousActivity) {
        for (const [queryKey, data] of context.previousActivity) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}

// DEC-042: Clear all failed jobs from history
export function useClearFailedActivity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => activityApi.clearFailed(),
    onMutate: async () => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['activity'] })

      // Snapshot previous value
      const previousActivity = queryClient.getQueriesData<ActivityList>({ queryKey: ['activity'] })

      // Optimistically remove all failed items
      queryClient.setQueriesData<ActivityList>({ queryKey: ['activity'] }, (old) => {
        if (!old) return old
        const filteredItems = old.items.filter((item) => item.status !== 'FAILED')
        return {
          ...old,
          items: filteredItems,
          total: filteredItems.length,
        }
      })

      return { previousActivity }
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousActivity) {
        for (const [queryKey, data] of context.previousActivity) {
          queryClient.setQueryData(queryKey, data)
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}
