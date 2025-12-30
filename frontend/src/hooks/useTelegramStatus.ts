import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { telegramApi } from '@/services/api'
import type {
  AuthStatusResponse,
  AuthStartRequest,
  AuthVerifyRequest,
  ChannelResolveRequest,
  TelegramConnectionStatus,
} from '@/types/telegram'

const TELEGRAM_STATUS_KEY = ['telegram', 'status']

export function useTelegramStatus() {
  const query = useQuery({
    queryKey: TELEGRAM_STATUS_KEY,
    queryFn: telegramApi.getAuthStatus,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Poll every 60 seconds
    retry: 1, // Only retry once on failure
  })

  // Derive connection status from query state and data
  const getConnectionStatus = (): TelegramConnectionStatus => {
    if (query.isError) {
      return 'unknown'
    }
    if (query.isLoading) {
      return 'connecting'
    }
    if (!query.data) {
      return 'unknown'
    }
    if (!query.data.configured) {
      return 'not_configured'
    }
    if (query.data.authenticated) {
      return 'connected'
    }
    return 'disconnected'
  }

  return {
    ...query,
    connectionStatus: getConnectionStatus(),
    user: query.data?.user ?? null,
    isAuthenticated: query.data?.authenticated ?? false,
    isConfigured: query.data?.configured ?? false,
    isConnected: query.data?.connected ?? false,
  }
}

export function useStartAuth() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: AuthStartRequest) => telegramApi.startAuth(data),
    onSuccess: () => {
      // Refetch status after starting auth
      queryClient.invalidateQueries({ queryKey: TELEGRAM_STATUS_KEY })
    },
  })
}

export function useVerifyAuth() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: AuthVerifyRequest) => telegramApi.verifyAuth(data),
    onSuccess: () => {
      // Refetch status after verification
      queryClient.invalidateQueries({ queryKey: TELEGRAM_STATUS_KEY })
    },
  })
}

export function useTelegramLogout() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: telegramApi.logout,
    onSuccess: () => {
      // Reset the status query data
      queryClient.setQueryData<AuthStatusResponse>(TELEGRAM_STATUS_KEY, {
        authenticated: false,
        configured: true,
        connected: false,
        user: null,
      })
    },
  })
}

export function useResolveChannel() {
  return useMutation({
    mutationFn: (data: ChannelResolveRequest) => telegramApi.resolveChannel(data),
  })
}

export function useChannelMessages(channelId: number | null, limit = 10) {
  return useQuery({
    queryKey: ['telegram', 'messages', channelId, limit],
    queryFn: () => telegramApi.getChannelMessages(channelId!, limit),
    enabled: !!channelId,
    staleTime: 30000, // 30 seconds
  })
}
