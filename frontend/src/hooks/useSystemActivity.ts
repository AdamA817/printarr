/**
 * React Query hook for system activity status (v0.7)
 */
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/services/api'

/**
 * Fetch system activity status with polling
 * Polls every 3 seconds when the window is visible
 */
export function useSystemActivity() {
  return useQuery({
    queryKey: ['system', 'activity'],
    queryFn: () => systemApi.activity(),
    refetchInterval: 3000, // Poll every 3 seconds
    refetchIntervalInBackground: false, // Don't poll when tab is hidden
    staleTime: 2000, // Consider data stale after 2 seconds
    retry: 1, // Limit retries since this is polled frequently
  })
}
