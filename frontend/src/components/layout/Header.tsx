import { useLocation } from 'react-router-dom'

interface HeaderProps {
  onMenuClick: () => void
}

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/channels': 'Channels',
  '/settings': 'Settings',
}

export function Header({ onMenuClick }: HeaderProps) {
  const location = useLocation()
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
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full bg-accent-success"
            title="System healthy"
          />
          <span className="text-sm text-text-secondary hidden sm:inline">
            Healthy
          </span>
        </div>
        <span className="text-sm text-text-muted">v0.1</span>
      </div>
    </header>
  )
}
