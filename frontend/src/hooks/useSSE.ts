/**
 * Server-Sent Events hook for real-time updates (#222)
 *
 * Connects to the backend SSE endpoint and broadcasts events
 * to React Query cache for instant UI updates.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type {
  SSEEvent,
  ConnectionStatus,
  JobProgressPayload,
  JobCompletedPayload,
  JobFailedPayload,
  JobCanceledPayload,
  DesignStatusChangedPayload,
  DesignCreatedPayload,
  JobCreatedPayload,
  JobStartedPayload,
} from '@/types/events'
import type { QueueItem, QueueList } from '@/types/queue'
import type { DesignList, DesignListItem, DesignStatus } from '@/types/design'

// Base API URL (without /api/v1 suffix for SSE)
const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/api\/v1\/?$/, '') || ''
const SSE_URL = `${API_BASE}/api/v1/events/`

// Reconnection settings
const INITIAL_RETRY_DELAY = 1000 // 1 second
const MAX_RETRY_DELAY = 30000 // 30 seconds
const RETRY_MULTIPLIER = 1.5

export interface UseSSEOptions {
  enabled?: boolean
}

export function useSSE(options: UseSSEOptions = {}) {
  const { enabled = true } = options
  const queryClient = useQueryClient()

  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null)

  const eventSourceRef = useRef<EventSource | null>(null)
  const retryDelayRef = useRef(INITIAL_RETRY_DELAY)
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isUnmountedRef = useRef(false)

  // Handle job progress event
  const handleJobProgress = useCallback(
    (payload: JobProgressPayload) => {
      // Update specific queue item with progress
      queryClient.setQueriesData<QueueList>(
        { queryKey: ['queue'] },
        (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            items: oldData.items.map((item: QueueItem) =>
              item.id === payload.job_id
                ? {
                    ...item,
                    progress: payload.progress,
                    progress_message: payload.progress_message,
                  }
                : item
            ),
          }
        }
      )
    },
    [queryClient]
  )

  // Handle job completed event
  const handleJobCompleted = useCallback(
    (payload: JobCompletedPayload) => {
      // Invalidate queue to remove completed job
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      // Invalidate activity to show new completed job
      queryClient.invalidateQueries({ queryKey: ['activity'] })
      // If has design, invalidate that too
      if (payload.design_id) {
        queryClient.invalidateQueries({ queryKey: ['design', payload.design_id] })
        queryClient.invalidateQueries({ queryKey: ['designs'] })
      }
      // Update stats
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
    [queryClient]
  )

  // Handle job failed event
  const handleJobFailed = useCallback(
    (payload: JobFailedPayload) => {
      // Update queue item to show failed status
      queryClient.setQueriesData<QueueList>(
        { queryKey: ['queue'] },
        (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            items: oldData.items.map((item: QueueItem) =>
              item.id === payload.job_id
                ? {
                    ...item,
                    status: 'FAILED' as const,
                    error_message: payload.error,
                  }
                : item
            ),
          }
        }
      )
      // Invalidate activity
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
    [queryClient]
  )

  // Handle job canceled event
  const handleJobCanceled = useCallback(
    (payload: JobCanceledPayload) => {
      // Remove from queue optimistically
      queryClient.setQueriesData<QueueList>(
        { queryKey: ['queue'] },
        (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            items: oldData.items.filter((item: QueueItem) => item.id !== payload.job_id),
            total: oldData.total - 1,
          }
        }
      )
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
    [queryClient]
  )

  // Handle design status changed event
  const handleDesignStatusChanged = useCallback(
    (payload: DesignStatusChangedPayload) => {
      const newStatus = payload.new_status as DesignStatus

      // Update in design list
      queryClient.setQueriesData<DesignList>(
        { queryKey: ['designs'] },
        (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            items: oldData.items.map((item: DesignListItem) =>
              item.id === payload.design_id
                ? { ...item, status: newStatus }
                : item
            ),
          }
        }
      )

      // Invalidate detail query for the design
      queryClient.invalidateQueries({ queryKey: ['design', payload.design_id] })
    },
    [queryClient]
  )

  // Handle design created event
  const handleDesignCreated = useCallback(
    (_payload: DesignCreatedPayload) => {
      // Just invalidate designs to show new design
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
    [queryClient]
  )

  // Handle job created event
  const handleJobCreated = useCallback(
    (_payload: JobCreatedPayload) => {
      // Invalidate queue to show new job
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      queryClient.invalidateQueries({ queryKey: ['queueStats'] })
    },
    [queryClient]
  )

  // Handle job started event
  const handleJobStarted = useCallback(
    (payload: JobStartedPayload) => {
      // Update queue item to show running status
      queryClient.setQueriesData<QueueList>(
        { queryKey: ['queue'] },
        (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            items: oldData.items.map((item: QueueItem) =>
              item.id === payload.job_id
                ? { ...item, status: 'RUNNING' as const }
                : item
            ),
          }
        }
      )
    },
    [queryClient]
  )

  // Handle queue updated event
  const handleQueueUpdated = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['queue'] })
    queryClient.invalidateQueries({ queryKey: ['queueStats'] })
  }, [queryClient])

  // Process incoming event
  const handleEvent = useCallback(
    (event: SSEEvent) => {
      setLastEvent(event)

      switch (event.type) {
        case 'job_created':
          handleJobCreated(event.payload as JobCreatedPayload)
          break
        case 'job_started':
          handleJobStarted(event.payload as JobStartedPayload)
          break
        case 'job_progress':
          handleJobProgress(event.payload as JobProgressPayload)
          break
        case 'job_completed':
          handleJobCompleted(event.payload as JobCompletedPayload)
          break
        case 'job_failed':
          handleJobFailed(event.payload as JobFailedPayload)
          break
        case 'job_canceled':
          handleJobCanceled(event.payload as JobCanceledPayload)
          break
        case 'design_status_changed':
          handleDesignStatusChanged(event.payload as DesignStatusChangedPayload)
          break
        case 'design_created':
          handleDesignCreated(event.payload as DesignCreatedPayload)
          break
        case 'design_updated':
        case 'design_deleted':
          // Just invalidate designs
          queryClient.invalidateQueries({ queryKey: ['designs'] })
          break
        case 'queue_updated':
          handleQueueUpdated()
          break
        case 'sync_status':
          // Update stats when sync happens
          queryClient.invalidateQueries({ queryKey: ['stats'] })
          queryClient.invalidateQueries({ queryKey: ['designs'] })
          break
        case 'heartbeat':
          // Just keep connection alive, no action needed
          break
      }
    },
    [
      queryClient,
      handleJobCreated,
      handleJobStarted,
      handleJobProgress,
      handleJobCompleted,
      handleJobFailed,
      handleJobCanceled,
      handleDesignStatusChanged,
      handleDesignCreated,
      handleQueueUpdated,
    ]
  )

  // Connect to SSE
  const connect = useCallback(() => {
    if (isUnmountedRef.current) return
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setStatus('connecting')

    const eventSource = new EventSource(SSE_URL)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      if (isUnmountedRef.current) return
      setStatus('connected')
      retryDelayRef.current = INITIAL_RETRY_DELAY
    }

    eventSource.onmessage = (event) => {
      if (isUnmountedRef.current) return
      try {
        const data = JSON.parse(event.data) as SSEEvent
        handleEvent(data)
      } catch (error) {
        console.error('Failed to parse SSE event:', error)
      }
    }

    eventSource.onerror = () => {
      if (isUnmountedRef.current) return
      eventSource.close()
      eventSourceRef.current = null
      setStatus('reconnecting')

      // Schedule reconnect with exponential backoff
      const delay = retryDelayRef.current
      retryDelayRef.current = Math.min(delay * RETRY_MULTIPLIER, MAX_RETRY_DELAY)

      retryTimeoutRef.current = setTimeout(() => {
        if (!isUnmountedRef.current) {
          connect()
        }
      }, delay)
    }
  }, [handleEvent])

  // Disconnect from SSE
  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setStatus('disconnected')
  }, [])

  // Setup effect
  useEffect(() => {
    isUnmountedRef.current = false

    if (enabled) {
      connect()
    }

    return () => {
      isUnmountedRef.current = true
      disconnect()
    }
  }, [enabled, connect, disconnect])

  return {
    status,
    lastEvent,
    reconnect: connect,
    disconnect,
  }
}
