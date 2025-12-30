import axios from 'axios'

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

export interface Channel {
  id: string
  identifier: string
  title: string
  telegram_id?: number
  status: 'PENDING' | 'ACTIVE' | 'ERROR' | 'DISABLED'
  download_mode: 'MANUAL' | 'NEW' | 'ALL'
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

export const channelsApi = {
  list: (params?: { page?: number; limit?: number }) =>
    api
      .get<PaginatedResponse<Channel>>('/channels', { params })
      .then((r) => r.data),

  get: (id: string) => api.get<Channel>(`/channels/${id}`).then((r) => r.data),

  create: (data: { identifier: string }) =>
    api.post<Channel>('/channels', data).then((r) => r.data),

  delete: (id: string) => api.delete(`/channels/${id}`),
}

export const healthApi = {
  check: () => api.get<{ status: string }>('/health').then((r) => r.data),
}
