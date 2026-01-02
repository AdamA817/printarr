import axios from 'axios'
import type {
  Channel,
  ChannelCreate,
  ChannelUpdate,
  ChannelList,
  DownloadMode,
  DownloadModePreviewResponse,
  DownloadModeRequest,
  DownloadModeResponse,
} from '@/types/channel'
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
  // v0.7 Preview & Tag types
  PreviewListResponse,
  UpdatePreviewRequest,
  UpdatePreviewResponse,
  TagListResponse,
  TagCategoriesResponse,
  DesignTag,
  AddTagsRequest,
  AddTagsResponse,
  RemoveTagResponse,
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
import type { SettingsMap, SettingValue } from '@/types/settings'
import type {
  DiscoveredChannelList,
  DiscoveredChannelListParams,
  DiscoveredChannel,
  AddDiscoveredChannelRequest,
  AddDiscoveredChannelResponse,
  DiscoveredChannelStats,
} from '@/types/discovered-channel'
import type {
  DashboardStatsResponse,
  CalendarResponse,
  QueueResponse as DashboardQueueResponse,
  StorageResponse,
} from '@/types/dashboard'
import type { SystemActivityResponse } from '@/types/system'
import type {
  ImportSource,
  ImportSourceDetail,
  ImportSourceCreate,
  ImportSourceUpdate,
  ImportSourceList,
  ImportSourceListParams,
  SyncTriggerRequest,
  SyncTriggerResponse,
  ImportHistoryResponse,
  ImportHistoryParams,
  ImportProfile,
  ImportProfileCreate,
  ImportProfileUpdate,
  ImportProfileList,
  ImportProfileUsage,
} from '@/types/import-source'

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

  // Download mode endpoints (v0.6)
  previewDownloadMode: (id: string, newMode: DownloadMode) =>
    api.get<DownloadModePreviewResponse>(`/channels/${id}/download-mode/preview`, {
      params: { new_mode: newMode },
    }).then((r) => r.data),

  updateDownloadMode: (id: string, request: DownloadModeRequest) =>
    api.post<DownloadModeResponse>(`/channels/${id}/download-mode`, request).then((r) => r.data),
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

// Settings API (v0.5)
export const settingsApi = {
  getAll: () =>
    api.get<SettingsMap>('/settings/').then((r) => r.data),

  get: (key: string) =>
    api.get<SettingValue>(`/settings/${key}`).then((r) => r.data),

  update: (key: string, value: string | number | boolean) =>
    api.put<SettingValue>(`/settings/${key}`, { value }).then((r) => r.data),
}

// Discovered Channels API (v0.6)
export const discoveredChannelsApi = {
  list: (params?: DiscoveredChannelListParams) =>
    api.get<DiscoveredChannelList>('/discovered-channels/', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<DiscoveredChannel>(`/discovered-channels/${id}`).then((r) => r.data),

  stats: () =>
    api.get<DiscoveredChannelStats>('/discovered-channels/stats').then((r) => r.data),

  add: (id: string, request?: AddDiscoveredChannelRequest) =>
    api.post<AddDiscoveredChannelResponse>(`/discovered-channels/${id}/add`, request).then((r) => r.data),

  dismiss: (id: string) =>
    api.delete(`/discovered-channels/${id}`),
}

// Dashboard API (v0.6)
export const dashboardApi = {
  stats: () =>
    api.get<DashboardStatsResponse>('/stats/dashboard').then((r) => r.data),

  calendar: (days = 14) =>
    api.get<CalendarResponse>('/stats/dashboard/calendar', { params: { days } }).then((r) => r.data),

  queue: () =>
    api.get<DashboardQueueResponse>('/stats/dashboard/queue').then((r) => r.data),

  storage: () =>
    api.get<StorageResponse>('/stats/dashboard/storage').then((r) => r.data),
}

// =============================================================================
// Previews API (v0.7)
// =============================================================================

export const previewsApi = {
  // Get all previews for a design
  listForDesign: (designId: string) =>
    api.get<PreviewListResponse>(`/previews/design/${designId}/`).then((r) => r.data),

  // Update a preview (set as primary, change sort order)
  update: (previewId: string, data: UpdatePreviewRequest) =>
    api.patch<UpdatePreviewResponse>(`/previews/${previewId}`, data).then((r) => r.data),

  // Delete a preview
  delete: (previewId: string) =>
    api.delete(`/previews/${previewId}`),

  // Auto-select the best preview as primary
  autoSelectPrimary: (designId: string) =>
    api.post(`/previews/design/${designId}/auto-select-primary`).then((r) => r.data),

  // Get the URL for a preview file
  getFileUrl: (filePath: string) => `/api/v1/previews/files/${filePath}`,
}

// =============================================================================
// Tags API (v0.7)
// =============================================================================

export interface TagSearchParams {
  q: string
  limit?: number
}

export const tagsApi = {
  // List all tags
  list: (category?: string, includeZeroUsage = true) =>
    api.get<TagListResponse>('/tags', {
      params: { category, include_zero_usage: includeZeroUsage },
    }).then((r) => r.data),

  // Get tags grouped by category
  categories: () =>
    api.get<TagCategoriesResponse>('/tags/categories').then((r) => r.data),

  // Search tags for autocomplete
  search: (params: TagSearchParams) =>
    api.get<TagListResponse>('/tags/search', { params }).then((r) => r.data),

  // Get tags for a specific design
  getForDesign: (designId: string) =>
    api.get<DesignTag[]>(`/tags/design/${designId}/`).then((r) => r.data),

  // Add tags to a design
  addToDesign: (designId: string, data: AddTagsRequest) =>
    api.post<AddTagsResponse>(`/tags/design/${designId}/`, data).then((r) => r.data),

  // Remove a tag from a design
  removeFromDesign: (designId: string, tagId: string) =>
    api.delete<RemoveTagResponse>(`/tags/design/${designId}/${tagId}`).then((r) => r.data),
}

// =============================================================================
// System API (v0.7)
// =============================================================================

export const systemApi = {
  // Get current system activity status
  activity: () =>
    api.get<SystemActivityResponse>('/system/activity').then((r) => r.data),
}

// =============================================================================
// Import Sources API (v0.8)
// =============================================================================

export const importSourcesApi = {
  // List all import sources
  list: (params?: ImportSourceListParams) =>
    api.get<ImportSourceList>('/import-sources/', { params }).then((r) => r.data),

  // Get single import source with details
  get: (id: string) =>
    api.get<ImportSourceDetail>(`/import-sources/${id}`).then((r) => r.data),

  // Create new import source
  create: (data: ImportSourceCreate) =>
    api.post<ImportSource>('/import-sources/', data).then((r) => r.data),

  // Update import source
  update: (id: string, data: ImportSourceUpdate) =>
    api.put<ImportSource>(`/import-sources/${id}`, data).then((r) => r.data),

  // Delete import source
  delete: (id: string, keepDesigns = true) =>
    api.delete(`/import-sources/${id}`, { params: { keep_designs: keepDesigns } }),

  // Trigger sync for an import source
  triggerSync: (id: string, request?: SyncTriggerRequest) =>
    api.post<SyncTriggerResponse>(`/import-sources/${id}/sync`, request).then((r) => r.data),

  // Get import history for a source
  getHistory: (id: string, params?: ImportHistoryParams) =>
    api.get<ImportHistoryResponse>(`/import-sources/${id}/history`, { params }).then((r) => r.data),
}

// =============================================================================
// Import Profiles API (v0.8)
// =============================================================================

export const importProfilesApi = {
  // List all import profiles
  list: () =>
    api.get<ImportProfileList>('/import-profiles/').then((r) => r.data),

  // Get single import profile
  get: (id: string) =>
    api.get<ImportProfile>(`/import-profiles/${id}`).then((r) => r.data),

  // Create new import profile
  create: (data: ImportProfileCreate) =>
    api.post<ImportProfile>('/import-profiles/', data).then((r) => r.data),

  // Update import profile
  update: (id: string, data: ImportProfileUpdate) =>
    api.put<ImportProfile>(`/import-profiles/${id}`, data).then((r) => r.data),

  // Delete import profile
  delete: (id: string) =>
    api.delete(`/import-profiles/${id}`),

  // Get usage info for a profile
  getUsage: (id: string) =>
    api.get<ImportProfileUsage>(`/import-profiles/${id}/usage`).then((r) => r.data),
}
