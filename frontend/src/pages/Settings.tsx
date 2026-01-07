import {
  LibrarySettings,
  DownloadSettings,
  TelegramSettings,
  SyncSettings,
  PreviewSettings,
  AiSettings,
} from '@/components/settings'

export function Settings() {
  return (
    <div className="space-y-6">
      {/* Settings Sections */}
      <LibrarySettings />
      <DownloadSettings />
      <TelegramSettings />
      <SyncSettings />
      <PreviewSettings />
      <AiSettings />
    </div>
  )
}
