import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/services/api'

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => dashboardApi.stats(),
    staleTime: 30000, // 30 seconds
    refetchInterval: 30000, // Refresh every 30 seconds
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
  return useQuery({
    queryKey: ['dashboard', 'queue'],
    queryFn: () => dashboardApi.queue(),
    staleTime: 5000, // 5 seconds
    refetchInterval: 5000, // Refresh every 5 seconds for near-realtime
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
