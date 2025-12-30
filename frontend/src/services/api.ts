import axios from 'axios'
import type { Channel, ChannelCreate, ChannelList } from '@/types/channel'

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

  delete: (id: string) => api.delete(`/channels/${id}`),
}

export const healthApi = {
  check: () => api.get<{ status: string }>('/health').then((r) => r.data),
}
