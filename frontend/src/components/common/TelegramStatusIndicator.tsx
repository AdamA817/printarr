import { useState } from 'react'
import { useTelegramStatus } from '@/hooks/useTelegramStatus'
import type { TelegramConnectionStatus } from '@/types/telegram'

interface TelegramStatusIndicatorProps {
  onClickDisconnected?: () => void
}

const statusConfig: Record<
  TelegramConnectionStatus,
  { color: string; label: string; description: string }
> = {
  connected: {
    color: 'bg-accent-success',
    label: 'TG',
    description: 'Connected to Telegram',
  },
  connecting: {
    color: 'bg-accent-warning',
    label: 'TG',
    description: 'Connecting to Telegram...',
  },
  disconnected: {
    color: 'bg-text-muted',
    label: 'TG',
    description: 'Click to connect to Telegram',
  },
  not_configured: {
    color: 'bg-accent-danger',
    label: 'TG',
    description: 'Telegram API not configured',
  },
  unknown: {
    color: 'bg-text-muted',
    label: 'TG',
    description: 'Unable to check Telegram status',
  },
}

export function TelegramStatusIndicator({
  onClickDisconnected,
}: TelegramStatusIndicatorProps) {
  const { connectionStatus, user, isLoading, refetch } = useTelegramStatus()
  const [showDropdown, setShowDropdown] = useState(false)

  const config = statusConfig[connectionStatus]

  const handleClick = () => {
    if (connectionStatus === 'disconnected' && onClickDisconnected) {
      onClickDisconnected()
    } else {
      setShowDropdown(!showDropdown)
    }
  }

  const isClickable =
    connectionStatus === 'disconnected' || connectionStatus === 'connected'

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        disabled={!isClickable}
        className={`
          flex items-center gap-2 px-2 py-1 rounded transition-colors
          ${isClickable ? 'hover:bg-bg-tertiary cursor-pointer' : 'cursor-default'}
          ${connectionStatus === 'disconnected' ? 'hover:bg-accent-primary/20' : ''}
        `}
        title={config.description}
        aria-label={config.description}
      >
        {/* Telegram Icon + Status Dot */}
        <div className="relative">
          <TelegramIcon className="w-5 h-5 text-text-secondary" />
          <span
            className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full border border-bg-secondary ${config.color} ${
              isLoading ? 'animate-pulse' : ''
            }`}
          />
        </div>

        {/* Label - hidden on small screens */}
        <span className="text-sm text-text-secondary hidden sm:inline">
          {config.label}
        </span>
      </button>

      {/* Dropdown for connected state */}
      {showDropdown && connectionStatus === 'connected' && (
        <>
          {/* Backdrop to close dropdown */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
          />
          <div className="absolute right-0 top-full mt-1 z-20 bg-bg-secondary border border-bg-tertiary rounded-lg shadow-lg min-w-[200px]">
            <div className="p-3 border-b border-bg-tertiary">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${config.color}`} />
                <span className="text-sm font-medium text-text-primary">
                  Connected
                </span>
              </div>
              {user && (
                <div className="mt-2 text-sm text-text-secondary">
                  {user.first_name && (
                    <div>
                      {user.first_name} {user.last_name}
                    </div>
                  )}
                  {user.username && <div>@{user.username}</div>}
                </div>
              )}
            </div>
            <div className="p-2">
              <button
                onClick={() => {
                  refetch()
                  setShowDropdown(false)
                }}
                className="w-full text-left px-3 py-2 text-sm text-text-secondary hover:bg-bg-tertiary rounded transition-colors"
              >
                Refresh Status
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// Simple Telegram icon component
function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.66-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.37-.49 1.02-.74 3.99-1.73 6.65-2.87 7.97-3.43 3.8-1.57 4.59-1.85 5.1-1.85.11 0 .37.03.53.17.14.12.18.28.2.45-.01.06.01.24 0 .38z" />
    </svg>
  )
}
