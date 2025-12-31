// Types for discovered channels (v0.6)
// Must match backend/app/schemas/discovered_channel.py

import type { BackfillMode, DownloadMode } from './channel'

export interface DiscoveredChannel {
  id: string
  telegram_peer_id: string | null
  title: string | null
  username: string | null
  invite_hash: string | null
  is_private: boolean
  reference_count: number
  first_seen_at: string
  last_seen_at: string
  source_types: string[]
  created_at: string
  updated_at: string
}

export interface DiscoveredChannelList {
  items: DiscoveredChannel[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DiscoveredChannelListParams {
  page?: number
  page_size?: number
  sort_by?: 'reference_count' | 'last_seen_at' | 'first_seen_at'
  sort_order?: 'asc' | 'desc'
  exclude_added?: boolean
}

export interface AddDiscoveredChannelRequest {
  download_mode?: DownloadMode
  backfill_mode?: BackfillMode
  backfill_value?: number
  is_enabled?: boolean
  remove_from_discovered?: boolean
}

export interface AddDiscoveredChannelResponse {
  channel_id: string
  title: string
  was_existing: boolean
}

export interface DiscoveredChannelStats {
  total: number
  new_this_week: number
  most_referenced: DiscoveredChannel[]
}
