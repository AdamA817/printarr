import { useInfiniteQuery } from '@tanstack/react-query'
import { designsApi } from '@/services/api'
import type { DesignListParams, DesignList } from '@/types/design'

/**
 * Hook for infinite scroll design list.
 * Uses useInfiniteQuery to load pages as user scrolls.
 */
export function useInfiniteDesigns(params?: Omit<DesignListParams, 'page'>) {
  return useInfiniteQuery<DesignList>({
    queryKey: ['designs', 'infinite', params],
    queryFn: ({ pageParam }) =>
      designsApi.list({ ...params, page: pageParam as number }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    getPreviousPageParam: (firstPage) =>
      firstPage.page > 1 ? firstPage.page - 1 : undefined,
  })
}

/**
 * Helper to flatten all pages into a single items array
 */
export function flattenInfiniteDesigns(data: { pages: DesignList[] } | undefined) {
  if (!data) return []
  return data.pages.flatMap((page) => page.items)
}

/**
 * Get total count from infinite query data
 */
export function getInfiniteDesignsTotal(data: { pages: DesignList[] } | undefined) {
  if (!data || data.pages.length === 0) return 0
  return data.pages[0].total
}
