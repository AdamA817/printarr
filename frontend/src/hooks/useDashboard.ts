import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/services/api'
import { useSSEStatus } from '@/contexts/SSEContext'

export function useDashboardStats() {
  const sseStatus = useSSEStatus()
  const isSSEConnected = sseStatus === 'connected'

  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => dashboardApi.stats(),
    staleTime: 30000, // 30 seconds
    // Reduce polling when SSE is connected - SSE triggers invalidation on changes
    refetchInterval: isSSEConnected ? 60000 : 30000,
  })
}

export function useDashboardCalendar(days = 14) {
  return useQuery({
    queryKey: ['dashboard', 'calendar', days],
    queryFn: () => dashboardApi.calendar(days),
    staleTime: 60000, // 1 minute
    refetchInterval: 60000, // Refresh every minute
  })
}

export function useDashboardQueue() {
  const sseStatus = useSSEStatus()
  const isSSEConnected = sseStatus === 'connected'

  return useQuery({
    queryKey: ['dashboard', 'queue'],
    queryFn: () => dashboardApi.queue(),
    staleTime: 5000, // 5 seconds
    // Only poll as fallback when SSE is disconnected - SSE handles real-time updates
    refetchInterval: isSSEConnected ? false : 5000,
  })
}

export function useDashboardStorage() {
  return useQuery({
    queryKey: ['dashboard', 'storage'],
    queryFn: () => dashboardApi.storage(),
    staleTime: 60000, // 1 minute
    refetchInterval: 60000, // Refresh every minute
  })
}
