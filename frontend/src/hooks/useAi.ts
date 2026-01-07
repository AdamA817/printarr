/**
 * AI Analysis Hooks (DEC-043)
 *
 * Provides React Query hooks for AI-powered design analysis
 * including single design analysis, bulk analysis, and settings.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { aiApi } from '@/services/api'

// Query keys
export const aiKeys = {
  all: ['ai'] as const,
  status: () => [...aiKeys.all, 'status'] as const,
  settings: () => [...aiKeys.all, 'settings'] as const,
}

/**
 * Get AI service status
 */
export function useAiStatus() {
  return useQuery({
    queryKey: aiKeys.status(),
    queryFn: aiApi.getStatus,
    staleTime: 60000, // 1 minute
  })
}

/**
 * Get AI settings for settings page
 */
export function useAiSettings() {
  return useQuery({
    queryKey: aiKeys.settings(),
    queryFn: aiApi.getSettings,
    staleTime: 30000, // 30 seconds
  })
}

/**
 * Update AI settings
 */
export function useUpdateAiSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: aiApi.updateSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(aiKeys.settings(), data)
    },
  })
}

/**
 * Analyze a single design with AI
 */
export function useAiAnalyze() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ designId, force }: { designId: string; force?: boolean }) =>
      aiApi.analyze(designId, { force }),
    onSuccess: (_data, { designId }) => {
      // Invalidate the design to refresh tags after analysis completes
      queryClient.invalidateQueries({ queryKey: ['design', designId] })
      queryClient.invalidateQueries({ queryKey: ['tags', 'design', designId] })
    },
  })
}

/**
 * Analyze multiple designs with AI (bulk operation)
 */
export function useAiBulkAnalyze() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ designIds, force }: { designIds: string[]; force?: boolean }) =>
      aiApi.bulkAnalyze({ design_ids: designIds, force }),
    onSuccess: (_data, { designIds }) => {
      // Invalidate all affected designs
      designIds.forEach((id) => {
        queryClient.invalidateQueries({ queryKey: ['design', id] })
        queryClient.invalidateQueries({ queryKey: ['tags', 'design', id] })
      })
      // Also invalidate the designs list
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}
