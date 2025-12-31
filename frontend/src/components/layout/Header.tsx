import { useLocation } from 'react-router-dom'
import { TelegramStatusIndicator } from '@/components/common/TelegramStatusIndicator'
import { useHealth } from '@/hooks/useHealth'

interface HeaderProps {
  onMenuClick: () => void
  onTelegramAuthClick?: () => void
}

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/designs': 'Designs',
  '/channels': 'Channels',
  '/activity': 'Activity',
  '/settings': 'Settings',
}

export function Header({ onMenuClick, onTelegramAuthClick }: HeaderProps) {
  const location = useLocation()
  const { data: health, isError } = useHealth()
  const title = pageTitles[location.pathname] || 'Printarr'

  return (
    <header className="h-14 bg-bg-secondary border-b border-bg-tertiary flex items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-4">
        {/* Mobile menu button */}
        <button
          onClick={onMenuClick}
          className="lg:hidden text-text-secondary hover:text-text-primary"
          aria-label="Open menu"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-4">
        {/* Telegram Status */}
        <TelegramStatusIndicator onClickDisconnected={onTelegramAuthClick} />

        {/* System Health */}
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${isError ? 'bg-accent-danger' : 'bg-accent-success'}`}
            title={isError ? 'System unhealthy' : 'System healthy'}
          />
          <span className="text-sm text-text-secondary hidden sm:inline">
            {isError ? 'Unhealthy' : 'Healthy'}
          </span>
        </div>

        {/* Version */}
        <span className="text-sm text-text-muted">
          {health?.version ? `v${health.version}` : '...'}
        </span>
      </div>
    </header>
  )
}
