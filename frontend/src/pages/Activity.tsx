import { useState } from 'react'
import { QueueView, HistoryView } from '@/components/activity'

type Tab = 'queue' | 'history'

export function Activity() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')

  return (
    <div className="space-y-6">
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
        {activeTab === 'history' && <HistoryView />}
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
