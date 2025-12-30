import axios from 'axios'
import type { Channel, ChannelCreate, ChannelUpdate, ChannelList } from '@/types/channel'
import type { DesignList, DesignListParams } from '@/types/design'
import type {
  AuthStatusResponse,
  AuthStartRequest,
  AuthStartResponse,
  AuthVerifyRequest,
  AuthVerifyResponse,
  AuthLogoutResponse,
  ChannelResolveRequest,
  ChannelResolveResponse,
  MessagesResponse,
} from '@/types/telegram'
import type { StatsResponse } from '@/types/stats'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export interface ChannelListParams {
  page?: number
  page_size?: number
  is_enabled?: boolean
}

export const channelsApi = {
  list: (params?: ChannelListParams) =>
    api.get<ChannelList>('/channels/', { params }).then((r) => r.data),

  get: (id: string) => api.get<Channel>(`/channels/${id}`).then((r) => r.data),

  create: (data: ChannelCreate) =>
    api.post<Channel>('/channels/', data).then((r) => r.data),

  update: (id: string, data: ChannelUpdate) =>
    api.patch<Channel>(`/channels/${id}`, data).then((r) => r.data),

  delete: (id: string) => api.delete(`/channels/${id}`),
}

export const healthApi = {
  check: () => api.get<{ status: string }>('/health').then((r) => r.data),
}

export const telegramApi = {
  getAuthStatus: () =>
    api.get<AuthStatusResponse>('/telegram/auth/status').then((r) => r.data),

  startAuth: (data: AuthStartRequest) =>
    api.post<AuthStartResponse>('/telegram/auth/start', data).then((r) => r.data),

  verifyAuth: (data: AuthVerifyRequest) =>
    api.post<AuthVerifyResponse>('/telegram/auth/verify', data).then((r) => r.data),

  logout: () =>
    api.post<AuthLogoutResponse>('/telegram/auth/logout').then((r) => r.data),

  resolveChannel: (data: ChannelResolveRequest) =>
    api.post<ChannelResolveResponse>('/telegram/channels/resolve', data).then((r) => r.data),

  getChannelMessages: (channelId: number, limit = 10) =>
    api.get<MessagesResponse>(`/telegram/channels/${channelId}/messages/`, { params: { limit } }).then((r) => r.data),
}

export const statsApi = {
  getStats: () => api.get<StatsResponse>('/stats/').then((r) => r.data),
}

export const designsApi = {
  list: (params?: DesignListParams) =>
    api.get<DesignList>('/designs/', { params }).then((r) => r.data),
}
