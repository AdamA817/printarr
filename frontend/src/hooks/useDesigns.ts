import { useQuery } from '@tanstack/react-query'
import { designsApi } from '@/services/api'
import type { DesignListParams } from '@/types/design'

export function useDesigns(params?: DesignListParams) {
  return useQuery({
    queryKey: ['designs', params],
    queryFn: () => designsApi.list(params),
  })
}
