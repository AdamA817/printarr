import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { designsApi } from '@/services/api'
import type {
  DesignListParams,
  ThangsLinkRequest,
  DesignUpdateRequest,
} from '@/types/design'

export function useDesigns(params?: DesignListParams) {
  return useQuery({
    queryKey: ['designs', params],
    queryFn: () => designsApi.list(params),
  })
}

export function useDesign(id: string) {
  return useQuery({
    queryKey: ['design', id],
    queryFn: () => designsApi.get(id),
    enabled: !!id,
  })
}

export function useUpdateDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DesignUpdateRequest }) =>
      designsApi.update(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['design', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

export function useLinkToThangs() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ThangsLinkRequest }) =>
      designsApi.linkToThangs(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['design', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

export function useLinkToThangsByUrl() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, url }: { id: string; url: string }) =>
      designsApi.linkToThangsByUrl(id, { url }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['design', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

export function useUnlinkFromThangs() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => designsApi.unlinkFromThangs(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['design', id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

export function useRefreshMetadata() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => designsApi.refreshMetadata(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['design', id] })
    },
  })
}

export function useMergeDesigns() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ targetId, sourceDesignIds }: { targetId: string; sourceDesignIds: string[] }) =>
      designsApi.merge(targetId, { source_design_ids: sourceDesignIds }),
    onSuccess: (data) => {
      // Invalidate the merged design and the list
      queryClient.invalidateQueries({ queryKey: ['design', data.merged_design_id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      // Also invalidate any deleted designs (they'll 404 if accessed)
      data.deleted_design_ids.forEach((id) => {
        queryClient.invalidateQueries({ queryKey: ['design', id] })
      })
    },
  })
}

export function useUnmergeDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ designId, sourceIds }: { designId: string; sourceIds: string[] }) =>
      designsApi.unmerge(designId, { source_ids: sourceIds }),
    onSuccess: (data) => {
      // Invalidate both the original and new design
      queryClient.invalidateQueries({ queryKey: ['design', data.original_design_id] })
      queryClient.invalidateQueries({ queryKey: ['design', data.new_design_id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}
