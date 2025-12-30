import { LibrarySettings, DownloadSettings } from '@/components/settings'

export function Settings() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
      </div>

      {/* Settings Sections */}
      <LibrarySettings />
      <DownloadSettings />
    </div>
  )
}
