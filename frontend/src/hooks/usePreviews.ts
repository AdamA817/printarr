/**
 * React Query hooks for preview image management (v0.7)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { previewsApi } from '@/services/api'
import type { UpdatePreviewRequest } from '@/types/design'

/**
 * Fetch all previews for a design
 */
export function useDesignPreviews(designId: string) {
  return useQuery({
    queryKey: ['previews', designId],
    queryFn: () => previewsApi.listForDesign(designId),
    enabled: !!designId,
    staleTime: 60000, // 1 minute
  })
}

/**
 * Update a preview (set as primary, change sort order)
 */
export function useUpdatePreview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ previewId, data }: { previewId: string; data: UpdatePreviewRequest }) =>
      previewsApi.update(previewId, data),
    onSuccess: () => {
      // Invalidate preview queries
      queryClient.invalidateQueries({ queryKey: ['previews'] })
      // Also invalidate design queries since primary_preview may change
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['design'] })
    },
  })
}

/**
 * Set a preview as primary
 */
export function useSetPrimaryPreview() {
  const updatePreview = useUpdatePreview()

  return useMutation({
    mutationFn: (previewId: string) =>
      updatePreview.mutateAsync({ previewId, data: { is_primary: true } }),
  })
}

/**
 * Delete a preview
 */
export function useDeletePreview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (previewId: string) => previewsApi.delete(previewId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['previews'] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['design'] })
    },
  })
}

/**
 * Auto-select the best preview as primary
 */
export function useAutoSelectPrimary() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (designId: string) => previewsApi.autoSelectPrimary(designId),
    onSuccess: (_, designId) => {
      queryClient.invalidateQueries({ queryKey: ['previews', designId] })
      queryClient.invalidateQueries({ queryKey: ['design', designId] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Helper to get the full URL for a preview file
 */
export function getPreviewUrl(filePath: string): string {
  return previewsApi.getFileUrl(filePath)
}
