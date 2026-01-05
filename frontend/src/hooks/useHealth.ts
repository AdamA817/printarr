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

// DEC-042: Detailed health check with subsystem status
export function useDetailedHealth() {
  return useQuery({
    queryKey: ['health', 'detailed'],
    queryFn: () => healthApi.detailed(),
    staleTime: 30 * 1000, // Consider fresh for 30 seconds
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
  })
}
