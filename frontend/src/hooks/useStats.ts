import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/services/api'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.getStats,
    staleTime: 30 * 1000, // Consider data fresh for 30 seconds
  })
}
