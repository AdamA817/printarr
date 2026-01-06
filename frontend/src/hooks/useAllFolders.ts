import { useQuery } from '@tanstack/react-query'
import { importSourcesApi } from '@/services/api'

/**
 * Hook for fetching all import source folders.
 * Used for filter dropdowns in the Designs page.
 */
export function useAllFolders(sourceId?: string) {
  return useQuery({
    queryKey: ['allFolders', sourceId],
    queryFn: () => importSourcesApi.listAllFolders(sourceId),
    staleTime: 60000, // Cache for 1 minute
  })
}
