/**
 * React Query hooks for tag management (v0.7)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tagsApi } from '@/services/api'
import type { TagSource } from '@/types/design'

/**
 * Fetch all available tags
 */
export function useTags(category?: string, includeZeroUsage = true) {
  return useQuery({
    queryKey: ['tags', { category, includeZeroUsage }],
    queryFn: () => tagsApi.list(category, includeZeroUsage),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Fetch tags grouped by category
 */
export function useTagCategories() {
  return useQuery({
    queryKey: ['tags', 'categories'],
    queryFn: () => tagsApi.categories(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Search tags for autocomplete
 */
export function useTagSearch(query: string, limit = 10) {
  return useQuery({
    queryKey: ['tags', 'search', query, limit],
    queryFn: () => tagsApi.search({ q: query, limit }),
    enabled: query.length >= 1,
    staleTime: 30000, // 30 seconds
  })
}

/**
 * Fetch tags for a specific design
 */
export function useDesignTags(designId: string) {
  return useQuery({
    queryKey: ['tags', 'design', designId],
    queryFn: () => tagsApi.getForDesign(designId),
    enabled: !!designId,
    staleTime: 60000, // 1 minute
  })
}

/**
 * Add tags to a design
 */
export function useAddTagsToDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      designId,
      tags,
      source = 'USER',
    }: {
      designId: string
      tags: string[]
      source?: TagSource
    }) => tagsApi.addToDesign(designId, { tags, source }),
    onSuccess: (_, { designId }) => {
      // Invalidate design tags
      queryClient.invalidateQueries({ queryKey: ['tags', 'design', designId] })
      // Invalidate tag list (usage counts may change)
      queryClient.invalidateQueries({ queryKey: ['tags'] })
      // Invalidate design queries
      queryClient.invalidateQueries({ queryKey: ['design', designId] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Remove a tag from a design
 */
export function useRemoveTagFromDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ designId, tagId }: { designId: string; tagId: string }) =>
      tagsApi.removeFromDesign(designId, tagId),
    onSuccess: (_, { designId }) => {
      // Invalidate design tags
      queryClient.invalidateQueries({ queryKey: ['tags', 'design', designId] })
      // Invalidate tag list (usage counts may change)
      queryClient.invalidateQueries({ queryKey: ['tags'] })
      // Invalidate design queries
      queryClient.invalidateQueries({ queryKey: ['design', designId] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}
