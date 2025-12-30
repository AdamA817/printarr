export type BackfillMode = 'NONE' | 'COUNT' | 'DAYS' | 'ALL'
export type DownloadMode = 'MANUAL' | 'NEW' | 'ALL'
export type TitleSource = 'FILENAME' | 'CAPTION' | 'CHANNEL'
export type DesignerSource = 'FILENAME' | 'CAPTION' | 'CHANNEL'

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
