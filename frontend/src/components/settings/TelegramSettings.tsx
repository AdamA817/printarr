import { useState, useEffect } from 'react'
import { useSettings, useUpdateSetting } from '@/hooks/useSettings'
import { useTelegramStatus } from '@/hooks/useTelegramStatus'
import {
  DEFAULT_TELEGRAM_RATE_LIMIT,
  DEFAULT_TELEGRAM_CHANNEL_SPACING,
} from '@/types/settings'

export function TelegramSettings() {
  const { data: settings, isLoading } = useSettings()
  const { isAuthenticated, isLoading: statusLoading } = useTelegramStatus()
  const updateSetting = useUpdateSetting()

  // Local state for form
  const [rateLimit, setRateLimit] = useState(DEFAULT_TELEGRAM_RATE_LIMIT)
  const [channelSpacing, setChannelSpacing] = useState(DEFAULT_TELEGRAM_CHANNEL_SPACING)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    if (settings) {
      setRateLimit((settings.telegram_rate_limit_rpm as number) ?? DEFAULT_TELEGRAM_RATE_LIMIT)
      setChannelSpacing((settings.telegram_channel_spacing as number) ?? DEFAULT_TELEGRAM_CHANNEL_SPACING)
    }
  }, [settings])

  // Track changes
  useEffect(() => {
    if (!settings) return
    setHasChanges(
      rateLimit !== ((settings.telegram_rate_limit_rpm as number) ?? DEFAULT_TELEGRAM_RATE_LIMIT) ||
      channelSpacing !== ((settings.telegram_channel_spacing as number) ?? DEFAULT_TELEGRAM_CHANNEL_SPACING)
    )
  }, [rateLimit, channelSpacing, settings])

  // Validation
  const rateLimitError = rateLimit < 10 || rateLimit > 100 ? 'Must be between 10 and 100' : null
  const spacingError = channelSpacing < 0.5 || channelSpacing > 10 ? 'Must be between 0.5 and 10' : null

  const handleSave = async () => {
    if (rateLimitError || spacingError) return

    setSaveStatus('saving')
    try {
      await Promise.all([
        updateSetting.mutateAsync({ key: 'telegram_rate_limit_rpm', value: rateLimit }),
        updateSetting.mutateAsync({ key: 'telegram_channel_spacing', value: channelSpacing }),
      ])
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save Telegram settings:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return <SettingsSkeleton title="Telegram Settings" />
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text-primary">
          Telegram Settings
        </h3>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          statusLoading
            ? 'bg-text-muted/20 text-text-muted'
            : isAuthenticated
              ? 'bg-accent-success/20 text-accent-success'
              : 'bg-accent-warning/20 text-accent-warning'
        }`}>
          {statusLoading ? 'Checking...' : isAuthenticated ? 'Connected' : 'Not Connected'}
        </span>
      </div>

      <div className="space-y-6">
        {/* Rate Limit */}
        <div>
          <label
            htmlFor="rate-limit"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Rate Limit (requests per minute)
          </label>
          <p className="text-sm text-text-secondary mb-3">
            Maximum API requests to Telegram per minute. Lower values reduce risk of rate limiting.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="rate-limit"
              type="range"
              min={10}
              max={100}
              step={5}
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
              className="flex-1 h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
            />
            <span className="w-16 text-right text-sm text-text-primary font-mono">{rateLimit} rpm</span>
          </div>
          {rateLimitError && (
            <p className="mt-2 text-sm text-accent-danger">{rateLimitError}</p>
          )}
        </div>

        {/* Channel Spacing */}
        <div>
          <label
            htmlFor="channel-spacing"
            className="block text-sm font-medium text-text-primary mb-2"
          >
            Channel Spacing (seconds)
          </label>
          <p className="text-sm text-text-secondary mb-3">
            Minimum delay between requests to the same channel. Prevents flood wait errors.
          </p>
          <div className="flex items-center gap-4">
            <input
              id="channel-spacing"
              type="range"
              min={0.5}
              max={10}
              step={0.5}
              value={channelSpacing}
              onChange={(e) => setChannelSpacing(Number(e.target.value))}
              className="flex-1 h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
            />
            <span className="w-16 text-right text-sm text-text-primary font-mono">{channelSpacing.toFixed(1)}s</span>
          </div>
          {spacingError && (
            <p className="mt-2 text-sm text-accent-danger">{spacingError}</p>
          )}
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!rateLimitError || !!spacingError || saveStatus === 'saving'}
              className="px-4 py-2 rounded bg-accent-primary text-white font-medium hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saveStatus === 'saving' ? 'Saving...' : 'Save Changes'}
            </button>
            {saveStatus === 'success' && (
              <span className="text-sm text-accent-success flex items-center gap-1">
                <CheckIcon className="w-4 h-4" />
                Saved
              </span>
            )}
            {saveStatus === 'error' && (
              <span className="text-sm text-accent-danger">
                Failed to save. Please try again.
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function SettingsSkeleton({ title }: { title: string }) {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="h-6 bg-bg-tertiary rounded w-40 mb-4" />
      <div className="space-y-6">
        {[...Array(2)].map((_, i) => (
          <div key={i}>
            <div className="h-4 bg-bg-tertiary rounded w-48 mb-2" />
            <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-3" />
            <div className="h-8 bg-bg-tertiary rounded w-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
