import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { designsApi } from '@/services/api'

/**
 * Hook for designer autocomplete with debounce.
 * Returns suggestions matching the search query.
 */
export function useDesignerAutocomplete(query: string, debounceMs = 300) {
  const [debouncedQuery, setDebouncedQuery] = useState(query)

  // Debounce the query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, debounceMs)

    return () => clearTimeout(timer)
  }, [query, debounceMs])

  return useQuery({
    queryKey: ['designers', debouncedQuery],
    queryFn: () => designsApi.getDesigners(debouncedQuery || undefined, 20),
    enabled: debouncedQuery.length >= 1, // Only search with at least 1 character
    staleTime: 30000, // Cache for 30 seconds
  })
}

/**
 * Hook for getting all designers (for dropdown population)
 */
export function useAllDesigners(limit = 100) {
  return useQuery({
    queryKey: ['designers', 'all', limit],
    queryFn: () => designsApi.getDesigners(undefined, limit),
    staleTime: 60000, // Cache for 1 minute
  })
}
