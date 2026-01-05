/**
 * React Query hook for system activity status (v0.7)
 */
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/services/api'

/**
 * Fetch system activity status with adaptive polling
 * Polls slower (10s) when jobs are active to reduce SQLite contention
 * Polls faster (5s) when idle
 */
export function useSystemActivity() {
  return useQuery({
    queryKey: ['system', 'activity'],
    queryFn: () => systemApi.activity(),
    refetchInterval: (query) => {
      // Poll slower during active jobs to reduce database contention
      const data = query.state.data
      const hasActiveJobs = data && !data.summary.is_idle
      return hasActiveJobs ? 10000 : 5000 // 10s when busy, 5s when idle
    },
    refetchIntervalInBackground: false, // Don't poll when tab is hidden
    staleTime: 4000, // Consider data stale after 4 seconds
    retry: 1, // Limit retries since this is polled frequently
  })
}
