// Must match backend/app/db/models/enums.py exactly
export type BackfillMode = 'ALL_HISTORY' | 'LAST_N_MESSAGES' | 'LAST_N_DAYS'
export type DownloadMode = 'DOWNLOAD_ALL' | 'DOWNLOAD_ALL_NEW' | 'MANUAL'
export type TitleSource = 'CAPTION' | 'FILENAME' | 'MANUAL'
export type DesignerSource = 'CAPTION' | 'CHANNEL' | 'MANUAL'

export interface Channel {
  id: string
  telegram_peer_id: string
  title: string
  username: string | null
  invite_link: string | null
  is_private: boolean
  is_enabled: boolean
  backfill_mode: BackfillMode
  backfill_value: number
  download_mode: DownloadMode
  library_template_override: string | null
  title_source_override: TitleSource | null
  designer_source_override: DesignerSource | null
  last_ingested_message_id: number | null
  last_backfill_checkpoint: number | null
  last_sync_at: string | null
  created_at: string
  updated_at: string
}

export interface ChannelCreate {
  title: string
  username?: string
  invite_link?: string
  is_private?: boolean
  telegram_peer_id?: string
  // Backfill settings (used for update after create)
  backfill_mode?: BackfillMode
  backfill_value?: number
  start_backfill?: boolean // UI-only: trigger backfill after creation
}

export interface ChannelUpdate {
  title?: string
  username?: string
  invite_link?: string
  is_private?: boolean
  is_enabled?: boolean
  backfill_mode?: BackfillMode
  backfill_value?: number
  download_mode?: DownloadMode
  library_template_override?: string | null
  title_source_override?: TitleSource | null
  designer_source_override?: DesignerSource | null
}

export interface ChannelList {
  items: Channel[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Download mode preview/update types (for confirmation flow)
export interface DownloadModePreviewResponse {
  channel_id: string
  current_mode: DownloadMode
  new_mode: DownloadMode
  designs_to_queue: number
}

export interface DownloadModeRequest {
  download_mode: DownloadMode
  confirm_bulk_download?: boolean
}

export interface DownloadModeResponse {
  channel_id: string
  download_mode: DownloadMode
  designs_queued: number
}
