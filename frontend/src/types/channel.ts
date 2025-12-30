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
}

export interface ChannelList {
  items: Channel[]
  total: number
  page: number
  page_size: number
  pages: number
}
