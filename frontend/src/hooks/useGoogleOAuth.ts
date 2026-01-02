/**
 * React Query hooks for Google OAuth operations (v0.8)
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { googleOAuthApi } from '@/services/api'
import type { GoogleOAuthCallbackParams } from '@/types/import-source'

const QUERY_KEYS = {
  oauthStatus: ['google', 'oauth', 'status'] as const,
  credentials: ['google', 'credentials'] as const,
  credentialsDetail: (id: string) => ['google', 'credentials', id] as const,
}

/**
 * Get Google OAuth configuration and authentication status
 */
export function useGoogleOAuthStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.oauthStatus,
    queryFn: googleOAuthApi.getStatus,
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * List all connected Google accounts
 */
export function useGoogleCredentials() {
  return useQuery({
    queryKey: QUERY_KEYS.credentials,
    queryFn: googleOAuthApi.listCredentials,
    staleTime: 60 * 1000, // 1 minute
  })
}

/**
 * Get specific credentials
 */
export function useGoogleCredentialsDetail(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.credentialsDetail(id),
    queryFn: () => googleOAuthApi.getCredentials(id),
    enabled: !!id,
  })
}

/**
 * Initiate OAuth flow
 */
export function useInitiateGoogleOAuth() {
  return useMutation({
    mutationFn: googleOAuthApi.initiate,
    // Note: The actual redirect happens in the component after getting the URL
  })
}

/**
 * Handle OAuth callback
 */
export function useGoogleOAuthCallback() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: GoogleOAuthCallbackParams) => googleOAuthApi.callback(params),
    onSuccess: () => {
      // Invalidate both status and credentials queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.oauthStatus })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.credentials })
    },
  })
}

/**
 * Revoke Google credentials
 */
export function useRevokeGoogleCredentials() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: googleOAuthApi.revokeCredentials,
    onSuccess: () => {
      // Invalidate credentials queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.oauthStatus })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.credentials })
    },
  })
}
