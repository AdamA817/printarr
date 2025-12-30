import { useLocation } from 'react-router-dom'

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/channels': 'Channels',
  '/settings': 'Settings',
}

export function Header() {
  const location = useLocation()
  const title = pageTitles[location.pathname] || 'Printarr'

  return (
    <header className="h-14 bg-bg-secondary border-b border-bg-tertiary flex items-center justify-between px-6">
      <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
      <div className="flex items-center gap-4">
        <span className="text-sm text-text-secondary">v0.1</span>
      </div>
    </header>
  )
}
