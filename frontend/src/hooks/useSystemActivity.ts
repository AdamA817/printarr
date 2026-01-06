/**
 * React Query hook for system activity status (v0.7)
 */
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/services/api'
import { useSSEStatus } from '@/contexts/SSEContext'

/**
 * Fetch system activity status with adaptive polling
 * When SSE is connected, polling is disabled (SSE handles real-time updates)
 * When SSE is disconnected (fallback), polls slower (10s) when busy, faster (5s) when idle
 */
export function useSystemActivity() {
  const sseStatus = useSSEStatus()
  const isSSEConnected = sseStatus === 'connected'

  return useQuery({
    queryKey: ['system', 'activity'],
    queryFn: () => systemApi.activity(),
    refetchInterval: (query) => {
      // No polling when SSE is connected - SSE handles real-time updates
      if (isSSEConnected) return false

      // Fallback polling when SSE is disconnected
      const data = query.state.data
      const hasActiveJobs = data && !data.summary.is_idle
      return hasActiveJobs ? 10000 : 5000 // 10s when busy, 5s when idle
    },
    refetchIntervalInBackground: false, // Don't poll when tab is hidden
    staleTime: 4000, // Consider data stale after 4 seconds
    retry: 1, // Limit retries since this is polled frequently
  })
}
