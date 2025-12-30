import { useQuery } from '@tanstack/react-query'
import { thangsApi, type ThangsSearchParams } from '@/services/api'

export function useThangsSearch(params: ThangsSearchParams | null) {
  return useQuery({
    queryKey: ['thangs-search', params?.q, params?.limit],
    queryFn: () => thangsApi.search(params!),
    enabled: !!params?.q && params.q.length >= 3,
    staleTime: 5 * 60 * 1000, // 5 minutes (matches backend cache)
    retry: false, // Don't retry on rate limit errors
  })
}
