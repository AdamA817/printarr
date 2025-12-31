import { NavLink } from 'react-router-dom'
import logoFull from '@/assets/logo-full.png'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/designs', label: 'Designs', icon: '🎨' },
  { to: '/channels', label: 'Channels', icon: '📡' },
  { to: '/activity', label: 'Activity', icon: '📥' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <aside
      className={`
        fixed inset-y-0 left-0 z-30 w-64 bg-bg-secondary border-r border-bg-tertiary flex flex-col
        transform transition-transform duration-200 ease-in-out
        lg:relative lg:translate-x-0
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      <div className="p-4 border-b border-bg-tertiary flex items-center justify-between">
        <div className="flex items-center">
          <img src={logoFull} alt="Printarr" className="h-8" />
        </div>
        <button
          onClick={onClose}
          className="lg:hidden text-text-secondary hover:text-text-primary"
          aria-label="Close menu"
        >
          ✕
        </button>
      </div>
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-accent-primary/20 text-accent-primary'
                      : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                  }`
                }
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
