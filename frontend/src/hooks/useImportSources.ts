/**
 * React Query hooks for Import Sources (v0.8)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { importSourcesApi } from '@/services/api'
import type {
  ImportSourceCreate,
  ImportSourceUpdate,
  ImportSourceListParams,
  SyncTriggerRequest,
  ImportHistoryParams,
} from '@/types/import-source'

/**
 * Fetch list of import sources
 */
export function useImportSources(params?: ImportSourceListParams) {
  return useQuery({
    queryKey: ['importSources', params],
    queryFn: () => importSourcesApi.list(params),
  })
}

/**
 * Fetch single import source with details
 */
export function useImportSource(id: string) {
  return useQuery({
    queryKey: ['importSource', id],
    queryFn: () => importSourcesApi.get(id),
    enabled: !!id,
  })
}

/**
 * Create a new import source
 */
export function useCreateImportSource() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ImportSourceCreate) => importSourcesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['importSources'] })
    },
  })
}

/**
 * Update an import source
 */
export function useUpdateImportSource() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ImportSourceUpdate }) =>
      importSourcesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['importSources'] })
      queryClient.invalidateQueries({ queryKey: ['importSource', variables.id] })
    },
  })
}

/**
 * Delete an import source
 */
export function useDeleteImportSource() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, keepDesigns = true }: { id: string; keepDesigns?: boolean }) =>
      importSourcesApi.delete(id, keepDesigns),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['importSources'] })
    },
  })
}

/**
 * Trigger sync for an import source
 */
export function useTriggerSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, request }: { id: string; request?: SyncTriggerRequest }) =>
      importSourcesApi.triggerSync(id, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['importSources'] })
      queryClient.invalidateQueries({ queryKey: ['importSource', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['importHistory', variables.id] })
      // Also invalidate designs since sync may have imported new ones
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    },
  })
}

/**
 * Fetch import history for a source
 */
export function useImportHistory(sourceId: string, params?: ImportHistoryParams) {
  return useQuery({
    queryKey: ['importHistory', sourceId, params],
    queryFn: () => importSourcesApi.getHistory(sourceId, params),
    enabled: !!sourceId,
  })
}
