import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/services/api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.check(),
    staleTime: 60 * 1000, // Consider fresh for 1 minute
    refetchInterval: 60 * 1000, // Refetch every minute
  })
}
