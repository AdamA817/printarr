import { useState } from 'react'
import { QueueView } from '@/components/activity/QueueView'

type Tab = 'queue' | 'history'

export function Activity() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Activity</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-bg-tertiary">
        <nav className="-mb-px flex gap-4">
          <TabButton
            active={activeTab === 'queue'}
            onClick={() => setActiveTab('queue')}
          >
            Queue
          </TabButton>
          <TabButton
            active={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
          >
            History
          </TabButton>
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'queue' && <QueueView />}
        {activeTab === 'history' && <HistoryPlaceholder />}
      </div>
    </div>
  )
}

interface TabButtonProps {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}

function TabButton({ active, onClick, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-accent-primary text-accent-primary'
          : 'border-transparent text-text-secondary hover:text-text-primary hover:border-text-muted'
      }`}
    >
      {children}
    </button>
  )
}

// Placeholder for History view (will be implemented in issue #88)
function HistoryPlaceholder() {
  return (
    <div className="bg-bg-secondary rounded-lg p-8 text-center">
      <HistoryIcon className="w-16 h-16 mx-auto text-text-muted mb-4" />
      <h3 className="text-lg font-medium text-text-primary mb-2">
        History Coming Soon
      </h3>
      <p className="text-text-secondary">
        View completed and failed downloads here.
      </p>
    </div>
  )
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}
