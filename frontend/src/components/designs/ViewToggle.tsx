import { useEffect } from 'react'

export type ViewMode = 'grid' | 'list'

interface ViewToggleProps {
  view: ViewMode
  onChange: (view: ViewMode) => void
}

export function ViewToggle({ view, onChange }: ViewToggleProps) {
  // Keyboard shortcuts: 'g' for grid, 'l' for list
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only trigger if not typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }
      if (e.key === 'g' || e.key === 'G') {
        onChange('grid')
      } else if (e.key === 'l' || e.key === 'L') {
        onChange('list')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onChange])

  return (
    <div className="flex items-center bg-bg-tertiary rounded-lg p-1">
      <button
        onClick={() => onChange('grid')}
        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
          view === 'grid'
            ? 'bg-accent-primary text-white'
            : 'text-text-secondary hover:text-text-primary'
        }`}
        title="Grid view (G)"
        aria-label="Grid view"
      >
        <GridIcon />
      </button>
      <button
        onClick={() => onChange('list')}
        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
          view === 'list'
            ? 'bg-accent-primary text-white'
            : 'text-text-secondary hover:text-text-primary'
        }`}
        title="List view (L)"
        aria-label="List view"
      >
        <ListIcon />
      </button>
    </div>
  )
}

function GridIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </svg>
  )
}

function ListIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  )
}
