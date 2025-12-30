// Telegram API types
// Must match backend/app/schemas/telegram.py

export interface TelegramUser {
  id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  phone: string | null
}

export interface AuthStatusResponse {
  authenticated: boolean
  configured: boolean
  connected: boolean
  user: TelegramUser | null
}

export interface AuthStartRequest {
  phone: string
}

export interface AuthStartResponse {
  status: 'code_required'
  phone_code_hash: string
}

export interface AuthVerifyRequest {
  phone: string
  code: string
  phone_code_hash: string
  password?: string
}

export interface AuthVerifyResponse {
  status: 'authenticated' | '2fa_required'
}

export interface AuthLogoutResponse {
  status: 'logged_out'
}

export interface TelegramErrorResponse {
  error: string
  message: string
  retry_after: number | null
}

// Connection status for UI display
export type TelegramConnectionStatus =
  | 'disconnected'    // Not authenticated, click to set up
  | 'not_configured'  // API credentials not set
  | 'connecting'      // Auth in progress
  | 'connected'       // Authenticated with Telegram
  | 'unknown'         // API not responding

// Channel Resolution types
export interface ChannelResolveRequest {
  link: string
}

export interface ChannelResolveResponse {
  id: number | null
  title: string
  username: string | null
  type: 'channel' | 'supergroup' | 'group'
  members_count: number | null
  photo_url: string | null
  is_invite: boolean
  invite_hash: string | null
}
