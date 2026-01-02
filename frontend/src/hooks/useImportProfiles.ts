/**
 * React Query hooks for Import Profiles (v0.8)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { importProfilesApi } from '@/services/api'
import type { ImportProfileCreate, ImportProfileUpdate } from '@/types/import-source'

/**
 * Fetch list of import profiles
 */
export function useImportProfiles() {
  return useQuery({
    queryKey: ['importProfiles'],
    queryFn: () => importProfilesApi.list(),
  })
}

/**
 * Fetch single import profile
 */
export function useImportProfile(id: string) {
  return useQuery({
    queryKey: ['importProfile', id],
    queryFn: () => importProfilesApi.get(id),
    enabled: !!id,
  })
}

/**
 * Create a new import profile
 */
export function useCreateImportProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ImportProfileCreate) => importProfilesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['importProfiles'] })
    },
  })
}

/**
 * Update an import profile
 */
export function useUpdateImportProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ImportProfileUpdate }) =>
      importProfilesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['importProfiles'] })
      queryClient.invalidateQueries({ queryKey: ['importProfile', variables.id] })
    },
  })
}

/**
 * Delete an import profile
 */
export function useDeleteImportProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => importProfilesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['importProfiles'] })
    },
  })
}

/**
 * Fetch usage info for a profile
 */
export function useImportProfileUsage(id: string) {
  return useQuery({
    queryKey: ['importProfileUsage', id],
    queryFn: () => importProfilesApi.getUsage(id),
    enabled: !!id,
  })
}
