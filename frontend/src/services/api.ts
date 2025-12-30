import axios from 'axios'
import type { Channel, ChannelCreate, ChannelUpdate, ChannelList } from '@/types/channel'
import type {
  DesignList,
  DesignListParams,
  DesignDetail,
  ThangsLinkRequest,
  ThangsLinkByUrlRequest,
  ThangsLinkResponse,
  RefreshMetadataResponse,
  DesignUpdateRequest,
  ThangsSearchResponse,
  MergeDesignsRequest,
  MergeDesignsResponse,
  UnmergeDesignRequest,
  UnmergeDesignResponse,
  WantDesignResponse,
  DownloadDesignResponse,
  CancelDownloadResponse,
} from '@/types/design'
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
import type {
  QueueList,
  QueueListParams,
  QueueStats,
  ActivityList,
  ActivityListParams,
} from '@/types/queue'

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

export interface BackfillRequest {
  mode?: string
  value?: number
}

export interface BackfillResponse {
  channel_id: string
  messages_processed: number
  designs_created: number
  last_message_id: number
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

  triggerBackfill: (id: string, request?: BackfillRequest) =>
    api.post<BackfillResponse>(`/channels/${id}/backfill`, request).then((r) => r.data),
}

export const healthApi = {
  // Health endpoint is at /api/health (not under /v1)
  check: () => axios.get<{ status: string; version: string }>('/api/health').then((r) => r.data),
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

  get: (id: string) =>
    api.get<DesignDetail>(`/designs/${id}`).then((r) => r.data),

  update: (id: string, data: DesignUpdateRequest) =>
    api.patch<DesignDetail>(`/designs/${id}`, data).then((r) => r.data),

  // Thangs link operations
  linkToThangs: (id: string, data: ThangsLinkRequest) =>
    api.post<ThangsLinkResponse>(`/designs/${id}/thangs-link`, data).then((r) => r.data),

  linkToThangsByUrl: (id: string, data: ThangsLinkByUrlRequest) =>
    api.post<ThangsLinkResponse>(`/designs/${id}/thangs-link-by-url`, data).then((r) => r.data),

  unlinkFromThangs: (id: string) =>
    api.delete(`/designs/${id}/thangs-link`),

  refreshMetadata: (id: string) =>
    api.post<RefreshMetadataResponse>(`/designs/${id}/refresh-metadata`).then((r) => r.data),

  // Merge/Unmerge operations
  merge: (id: string, data: MergeDesignsRequest) =>
    api.post<MergeDesignsResponse>(`/designs/${id}/merge`, data).then((r) => r.data),

  unmerge: (id: string, data: UnmergeDesignRequest) =>
    api.post<UnmergeDesignResponse>(`/designs/${id}/unmerge`, data).then((r) => r.data),

  // Download actions (v0.5)
  want: (id: string) =>
    api.post<WantDesignResponse>(`/designs/${id}/want`).then((r) => r.data),

  download: (id: string) =>
    api.post<DownloadDesignResponse>(`/designs/${id}/download`).then((r) => r.data),

  cancelDownload: (id: string) =>
    api.post<CancelDownloadResponse>(`/designs/${id}/cancel`).then((r) => r.data),
}

export interface ThangsSearchParams {
  q: string
  limit?: number
}

export const thangsApi = {
  search: (params: ThangsSearchParams) =>
    api.get<ThangsSearchResponse>('/thangs/search', { params }).then((r) => r.data),
}

// Queue API (v0.5)
export const queueApi = {
  list: (params?: QueueListParams) =>
    api.get<QueueList>('/queue/', { params }).then((r) => r.data),

  stats: () =>
    api.get<QueueStats>('/queue/stats').then((r) => r.data),

  updatePriority: (jobId: string, priority: number) =>
    api.patch(`/queue/${jobId}`, { priority }).then((r) => r.data),

  cancel: (jobId: string) =>
    api.delete(`/queue/${jobId}`).then((r) => r.data),
}

// Activity API (v0.5)
export const activityApi = {
  list: (params?: ActivityListParams) =>
    api.get<ActivityList>('/activity/', { params }).then((r) => r.data),

  remove: (jobId: string) =>
    api.delete(`/activity/${jobId}`).then((r) => r.data),
}
