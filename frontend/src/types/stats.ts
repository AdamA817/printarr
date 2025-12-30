// Dashboard statistics types
// Must match backend/app/schemas/stats.py

export interface StatsResponse {
  channels_count: number
  designs_count: number
  downloads_active: number
}
