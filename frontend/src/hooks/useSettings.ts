import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/services/api'
import type { SettingsMap } from '@/types/settings'
import {
  DEFAULT_FOLDER_TEMPLATE,
  DEFAULT_MAX_CONCURRENT_DOWNLOADS,
  DEFAULT_DELETE_ARCHIVES,
} from '@/types/settings'

// Query key
export const settingsKeys = {
  all: ['settings'] as const,
  single: (key: string) => ['settings', key] as const,
}

// Hook to get all settings
export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: () => settingsApi.getAll(),
    staleTime: 30000, // Consider fresh for 30 seconds
  })
}

// Hook to update a single setting
export function useUpdateSetting() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string | number | boolean }) =>
      settingsApi.update(key, value),
    onMutate: async ({ key, value }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: settingsKeys.all })

      // Snapshot the previous value
      const previousSettings = queryClient.getQueryData<SettingsMap>(settingsKeys.all)

      // Optimistically update to the new value
      if (previousSettings) {
        queryClient.setQueryData<SettingsMap>(settingsKeys.all, {
          ...previousSettings,
          [key]: value,
        })
      }

      return { previousSettings }
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsKeys.all, context.previousSettings)
      }
    },
    onSettled: () => {
      // Invalidate to refetch fresh data
      queryClient.invalidateQueries({ queryKey: settingsKeys.all })
    },
  })
}

// Helper hook to get parsed settings with defaults
export function useLibrarySettings() {
  const { data: settings, isLoading, error } = useSettings()

  const librarySettings = {
    folder_template: (settings?.folder_template as string) ?? DEFAULT_FOLDER_TEMPLATE,
    max_concurrent_downloads:
      (settings?.max_concurrent_downloads as number) ?? DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    delete_archives_after_extraction:
      (settings?.delete_archives_after_extraction as boolean) ?? DEFAULT_DELETE_ARCHIVES,
  }

  return {
    settings: librarySettings,
    isLoading,
    error,
  }
}
