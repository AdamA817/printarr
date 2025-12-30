import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { designsApi } from '@/services/api'
import type {
  DesignListParams,
  ThangsLinkRequest,
  DesignUpdateRequest,
  DesignList,
  DesignListItem,
  DesignDetail,
  DesignStatus,
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

// Helper to update design status in cache
function updateDesignStatusInCache(
  queryClient: ReturnType<typeof useQueryClient>,
  designId: string,
  newStatus: DesignStatus
) {
  // Update in list queries
  queryClient.setQueriesData<DesignList>(
    { queryKey: ['designs'] },
    (oldData) => {
      if (!oldData) return oldData
      return {
        ...oldData,
        items: oldData.items.map((item: DesignListItem) =>
          item.id === designId ? { ...item, status: newStatus } : item
        ),
      }
    }
  )

  // Update in detail query
  queryClient.setQueryData<DesignDetail>(
    ['design', designId],
    (oldData) => {
      if (!oldData) return oldData
      return { ...oldData, status: newStatus }
    }
  )
}

// Mark design as wanted (queues for download)
export function useWantDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => designsApi.want(id),
    onMutate: async (id) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['designs'] })
      await queryClient.cancelQueries({ queryKey: ['design', id] })

      // Snapshot previous value for rollback
      const previousDesigns = queryClient.getQueriesData<DesignList>({ queryKey: ['designs'] })
      const previousDesign = queryClient.getQueryData<DesignDetail>(['design', id])

      // Optimistically update to WANTED
      updateDesignStatusInCache(queryClient, id, 'WANTED')

      return { previousDesigns, previousDesign }
    },
    onError: (_err, id, context) => {
      // Rollback on error
      if (context?.previousDesigns) {
        context.previousDesigns.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data)
        })
      }
      if (context?.previousDesign) {
        queryClient.setQueryData(['design', id], context.previousDesign)
      }
    },
    onSettled: (_data, _error, id) => {
      // Always refetch to ensure data is correct
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['design', id] })
    },
  })
}

// Force immediate download
export function useDownloadDesign() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => designsApi.download(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['designs'] })
      await queryClient.cancelQueries({ queryKey: ['design', id] })

      const previousDesigns = queryClient.getQueriesData<DesignList>({ queryKey: ['designs'] })
      const previousDesign = queryClient.getQueryData<DesignDetail>(['design', id])

      // Optimistically update to DOWNLOADING
      updateDesignStatusInCache(queryClient, id, 'DOWNLOADING')

      return { previousDesigns, previousDesign }
    },
    onError: (_err, id, context) => {
      if (context?.previousDesigns) {
        context.previousDesigns.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data)
        })
      }
      if (context?.previousDesign) {
        queryClient.setQueryData(['design', id], context.previousDesign)
      }
    },
    onSettled: (_data, _error, id) => {
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['design', id] })
    },
  })
}

// Cancel pending/in-progress download
export function useCancelDownload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => designsApi.cancelDownload(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['designs'] })
      await queryClient.cancelQueries({ queryKey: ['design', id] })

      const previousDesigns = queryClient.getQueriesData<DesignList>({ queryKey: ['designs'] })
      const previousDesign = queryClient.getQueryData<DesignDetail>(['design', id])

      // Optimistically update back to DISCOVERED
      updateDesignStatusInCache(queryClient, id, 'DISCOVERED')

      return { previousDesigns, previousDesign }
    },
    onError: (_err, id, context) => {
      if (context?.previousDesigns) {
        context.previousDesigns.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data)
        })
      }
      if (context?.previousDesign) {
        queryClient.setQueryData(['design', id], context.previousDesign)
      }
    },
    onSettled: (_data, _error, id) => {
      queryClient.invalidateQueries({ queryKey: ['designs'] })
      queryClient.invalidateQueries({ queryKey: ['design', id] })
    },
  })
}
