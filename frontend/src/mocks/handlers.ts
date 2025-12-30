import { http, HttpResponse } from 'msw'

// Mock data
const mockChannels = {
  items: [
    {
      id: '1',
      telegram_peer_id: '123456',
      title: 'Test Channel',
      username: 'testchannel',
      invite_link: null,
      is_private: false,
      is_enabled: true,
      backfill_mode: 'ALL_HISTORY' as const,
      backfill_value: 0,
      download_mode: 'MANUAL' as const,
      library_template_override: null,
      title_source_override: null,
      designer_source_override: null,
      last_ingested_message_id: null,
      last_backfill_checkpoint: null,
      last_sync_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
  pages: 1,
}

const mockAuthStatus = {
  authenticated: false,
  configured: true,
  connected: false,
  user: null,
}

const mockStats = {
  channels_count: 1,
  designs_count: 0,
  downloads_active: 0,
}

export const handlers = [
  // Channels endpoints
  http.get('/api/v1/channels/', () => {
    return HttpResponse.json(mockChannels)
  }),

  http.get('/api/v1/channels/:id', ({ params }) => {
    const channel = mockChannels.items.find((c) => c.id === params.id)
    if (channel) {
      return HttpResponse.json(channel)
    }
    return new HttpResponse(null, { status: 404 })
  }),

  http.post('/api/v1/channels/', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    const newChannel = {
      ...mockChannels.items[0],
      id: '2',
      title: body.title as string,
      username: body.username as string | undefined,
    }
    return HttpResponse.json(newChannel, { status: 201 })
  }),

  http.delete('/api/v1/channels/:id', () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // Telegram auth endpoints
  http.get('/api/v1/telegram/auth/status', () => {
    return HttpResponse.json(mockAuthStatus)
  }),

  // Health endpoint
  http.get('/api/v1/health', () => {
    return HttpResponse.json({ status: 'healthy' })
  }),

  // Stats endpoint
  http.get('/api/v1/stats/', () => {
    return HttpResponse.json(mockStats)
  }),
]
